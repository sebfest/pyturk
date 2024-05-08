import logging
import re

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, List, Set, Union

from .client import MTurkClient
from .exceptions import InsufficientFundingError

logger = logging.getLogger()
logger.addHandler(logging.NullHandler())


@dataclass(frozen=True)
class Qualification:
    _DESCRIPTION = (
        "This qualification was assigned to you based"
        " on your participation history."
        " Do not request this qualification type."
    )

    name: str
    description: Optional[str] = _DESCRIPTION
    identifier: Optional[str] = ''
    status: Optional[str] = 'Active'


@dataclass
class Assignment:
    assignment_id: str
    worker_id: str
    bonus: str
    reason: Optional[str] = None
    approve: Optional[int] = None
    assignment_status: Optional[str] = None
    answer: Optional[List] = None

    def __post_init__(self):
        self.unique_token = f'{self.worker_id}_{self.assignment_id}'
        
        if self.approve and not isinstance(self.approve, int):
            try:
                self.approve = int(self.approve)
            except TypeError as e:
                logger.error(e)
                raise

    @classmethod
    def from_dict(cls, assignment: Dict[str, Union[str, int, datetime]]):
        return cls(
            assignment_id=assignment['AssignmentId'],
            worker_id=assignment['WorkerId'],
            bonus=assignment.get('BonusAmount', ''),
            reason=assignment.get('Reason', ''),
            approve=assignment.get('Approve'),
            assignment_status=assignment.get('AssignmentStatus', ''),
            answer=re.findall(r'([0-9]{6})', assignment.get('Answer', '')),
        )

    def process(self, connection) -> None:
        """Approve or reject assignment."""
        if self.approve is None:
            logger.info("No status set")
        elif self.approve:
            func = connection.approve_assignment
            message = "Thank you for your work."
        elif not self.approve:
            func = connection.reject_assignment
            message = "You have submitted the assignment but not worked on it."
        else:
            logger.info("No valid value")
            
        try:
            func(
                AssignmentId=self.assignment_id,
                RequesterFeedback=message,
            )
        except Exception as error:
            logger.info("%s", error)
        else:
            logger.info(f'{self.worker_id}: {message}')

    def assign_qualification(self, connection, qualification: Qualification) -> None:
        """Assign qualification to worker."""
        try:
            connection.associate_qualification_with_worker(
                QualificationTypeId=qualification.identifier,
                WorkerId=self.worker_id,
                IntegerValue=1,
                SendNotification=False,
            )
        except Exception as error:
            logging.error(error)
        else:
            logger.info(
                "Qualification assigned to %s",
                self.worker_id
            )

    def get_bonus_report(self, connection) -> Dict[str, str]:
        """Retrieve amounts of bonuses paid to Worker."""
        try:
            payments = connection.list_bonus_payments(
                AssignmentId=self.assignment_id
            )['BonusPayments']
        except Exception as error:
            logging.error(error)
        else:
            return payments

    def pay_bonus(self, connection) -> None:
        """Deposit bonus payment to worker."""
        logger.info(
            "Granting %s$ to %s for %s",
            self.bonus,
            self.worker_id,
            self.assignment_id
        )
        try:
            connection.send_bonus(
                WorkerId=self.worker_id,
                BonusAmount=str(self.bonus),
                AssignmentId=self.assignment_id,
                Reason=self.reason,
                UniqueRequestToken=self.unique_token,
            )
        except Exception as error:
            logging.error(error)
        else:
            logger.info("Success")


class Hit:
    """A basic HIT class"""

    def __init__(
            self,
            hit_id: str,
            assignments: List[Assignment],
            sandbox: bool = True,
    ):

        self.hit_id = hit_id
        self.assignments = assignments if assignments else []
        self._sandbox: sandbox
        self._client: MTurkClient = MTurkClient(sandbox=sandbox)
        self.qualifications: Optional[Set[Qualification]] = set()

    def __repr__(self) -> str:
        return f'{type(self).__name__}(hit_id={self.hit_id!r})'

    def process_assignments(self) -> None:
        """Process assignments."""
        with self._client as connection:
            for assignment in self.assignments:
                assignment.process(connection)

    def add_qualification_to_hit(self, qualification: Qualification) -> None:
        """Add qualification to Hit."""
        self.qualifications.add(qualification)
        logger.info('Qualification attached to HIT.')

    def assign_qualification_to_workers(self) -> None:
        """Assign qualification to worker."""
        if not self.qualifications:
            logger.info('No qualification attached to HIT.')
            return

        with self._client as connection:
            for assignment in self.assignments:
                for qualification in self.qualifications:
                    assignment.assign_qualification(connection, qualification)
            logger.info("Qualification assignment completed")

    def _get_valid_assignments(self) -> List[Assignment]:
        """Filter assignments that have not been paid in the past."""
        valid_assignments: List[Assignment] = []
        with self._client as connection:
            for assignment in self.assignments:
                logger.info(
                    f'Checking previous payments for {assignment.assignment_id}'
                )
                payments = assignment.get_bonus_report(connection=connection)
                if payments:
                    logger.info(
                        f"{assignment.assignment_id} has been paid {payments['BonusAmount']}."
                    )
                else:
                    valid_assignments.append(assignment)
        return valid_assignments

    def get_balance(self) -> Decimal:
        """Check account balance"""
        with self._client as connection:
            balance = Decimal(connection.get_account_balance()['AvailableBalance'])
            logger.info(f'Your account balance is {balance}')
        return balance

    def check_account_balance(self, costs: Decimal) -> None:
        """Check is costs are covered."""
        balance = self.get_balance()
        if costs > balance:
            deficit = (costs - balance).quantize(Decimal('.01'), ROUND_HALF_UP)
            raise InsufficientFundingError(
                f'Your account balance is insufficient. You lack {deficit} USD'
            )
        else:
            remainder = (balance - costs).quantize(Decimal('.01'), ROUND_HALF_UP)
            logger.info(f'{remainder} will remain on your account')

    @staticmethod
    def calculate_bonus_costs(assignments: List[Assignment]) -> Decimal:
        """Calculates bonus amount"""
        bonuses = sum(
            Decimal(assignment.bonus).quantize(Decimal('.01'), ROUND_HALF_UP)
            for assignment in assignments
        )
        fees = (Decimal(0.2) * bonuses).quantize(Decimal('.01'), ROUND_HALF_UP)
        total_costs = (bonuses + fees).quantize(Decimal('.01'), ROUND_HALF_UP)
        logger.info(
            "The sum of all bonuses is %s USD, with %s USD in fees, you'll have to pay %s USD",
            bonuses,
            fees,
            total_costs,
        )
        return total_costs

    def make_bonus_payments(self, filter_previous=False):
        """Deposit bonus payments to workers."""
        valid_assignments = self._get_valid_assignments() if filter_previous else self.assignments
        total_costs = self.calculate_bonus_costs(assignments=valid_assignments)
        self.check_account_balance(total_costs)

        answer = input("If you want to continue, type 'Yes'. ")
        if not answer == "Yes":
            logger.info("Bonus payment canceled")
            return

        with self._client as connection:
            for assignment in valid_assignments:
                assignment.pay_bonus(connection)
            logger.info("Bonus payment finished")


