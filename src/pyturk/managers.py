import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from tabulate import tabulate

from pyturk.client import MTurkClient
from pyturk.exceptions import InputError
from pyturk.models import Hit, Assignment, Qualification

logger = logging.getLogger()
logger.addHandler(logging.NullHandler())


class BaseManager:

    def __init__(self, sandbox: bool = True):
        self._sandbox = sandbox
        self._client: MTurkClient = MTurkClient(sandbox=sandbox)

    def __repr__(self) -> str:
        return f'{type(self).__name__}(sandbox={self._sandbox!r})'

    @staticmethod
    def _get_item(choice_list: List[Dict[str, Any]]) -> dict[str, any]:
        """Choose item from list."""
        while True:
            user_input = input('Type inn your selection (q to quit): ')
            if 'q' in user_input.lower():
                raise InputError('User defined exit.')
            else:
                try:
                    choice = choice_list[int(user_input)]
                except IndexError:
                    print(f'{int(user_input)} out of range.')
                except ValueError:
                    print(f'{user_input} is not a valid number.')
                except Exception as error:
                    print(f'Unknown error occurred: f{error}.')
                else:
                    return choice


class HitManager(BaseManager):

    def _list_all_hits(self) -> List[Dict[str, Any]]:
        """List all reviewable HITs from MTurk."""
        with self._client as client:
            logger.info("Retrieving all HITs")
            paginator = client.get_paginator('list_hits')
            try:
                pages = paginator.paginate()
            except Exception as error:
                logging.error("%s", error)
            else:
                full_results = pages.build_full_result()
                return full_results['HITs']

    def _get_hit_id(self) -> str:
        """Get HITId from MTurk."""
        hits = self._list_all_hits()

        header = ['Number', 'CreationTime', 'HITId', 'Title']
        data = [
            (
                index,
                hit['CreationTime'].strftime("%Y/%m/%d %H:%M:%S"),
                hit['HITId'],
                hit['Title'],
            )
            for index, hit in enumerate(hits)
        ]
        print(tabulate(data, headers=header))
        hit = self._get_item(hits)
        return hit['HITId']

    def _get_assignments(self, hit_id: str) -> List[Assignment]:
        """Collect all assignments for a reviewable HIT."""
        with self._client as client:
            logger.info('Retrieving all assignments')
            paginator = client.get_paginator('list_assignments_for_hit')

            try:
                pages = paginator.paginate(HITId=hit_id)
            except AttributeError as error:
                logging.error("No hit set", error)
            except Exception as error:
                logging.error("%s", error)
            else:
                full_results = pages.build_full_result()
                assignments = full_results['Assignments']
                return [Assignment.from_dict(ass) for ass in assignments]

    def download_hit(self) -> Hit:
        """Retrieve assignments from MTurk"""
        hit_id = self._get_hit_id()

        logger.info('Downloading assignments.')
        assignments = self._get_assignments(
            hit_id=hit_id,
        )
        hit = Hit(
            hit_id=hit_id,
            assignments=assignments,
            sandbox=self._sandbox,
        )
        return hit

    def extend_hit(self, additional: int) -> None:
        """Create additional assignments for your HIT."""
        hit_id = self._get_hit_id()
        with self._client as client:
            try:
                client.create_additional_assignments_for_hit(
                    HITId=hit_id,
                    NumberOfAdditionalAssignments=int(additional),
                )
            except Exception as error:
                logging.error("%s", error)
            else:
                logger.info(f'{additional} additional assignments created.')

    def remove_hit(self) -> None:
        """Remove HIT from interface."""
        hit_id = self._get_hit_id()
        with self._client as client:
            try:
                client.delete_hit(HITId=hit_id)
            except Exception as error:
                logging.error(f'{error}')
            else:
                logger.info(f'{hit_id} removed.')

    def close_hit(self) -> None:
        """Close HIT (expire HIT)."""
        hit_id = self._get_hit_id()
        with self._client as client:
            try:
                client.update_expiration_for_hit(
                    HITId=hit_id,
                    ExpireAt=datetime.utcnow() - timedelta(days=1)
                )
            except Exception as error:
                logging.error(f'{error}')
            else:
                logger.info("Hit closed")

    def get_bonus_report_for_hit(self) -> List[Assignment]:
        """List amount of bonus paid to workers."""
        hit_id = self._get_hit_id()

        with self._client as client:
            logger.info("Retrieving all bonus payments")
            paginator = client.get_paginator('list_bonus_payments')

            try:
                pages = paginator.paginate(HITId=hit_id)
            except Exception as error:
                logging.error(f'{error}')
            else:
                full_results = pages.build_full_result()
                bonus_report = [
                    Assignment.from_dict(payment_report)
                    for payment_report in full_results['BonusPayments']
                ]
                return bonus_report

    def create_hit(self):
        """Create hit"""
        raise NotImplementedError()


class QualificationManager(BaseManager):

    def _list_all_qualifications(self) -> List[Dict[str, Any]]:
        """Retrieve Information of all Qualifications on MTurk."""
        with self._client as client:
            logger.info('Retrieving all qualifications')

            paginator = client.get_paginator('list_qualification_types')
            config = {'MaxItems': 50, 'PageSize': 50}
            page_iterator = paginator.paginate(
                MustBeRequestable=False,
                MustBeOwnedByCaller=True,
                PaginationConfig=config,
            )

            full_results = page_iterator.build_full_result()
            qualifications = full_results['QualificationTypes']

            return qualifications

    def _download_qualification(self) -> Dict[str, Any]:
        """Select single Qualification from MTurk."""
        qualifications = self._list_all_qualifications()

        header = ['Number', 'Name', 'CreationTime', 'Description']
        data = [(
            index,
            qualification['Name'],
            qualification['CreationTime'].strftime("%Y/%m/%d %H:%M:%S"),
            qualification['Description'][:60],
        )
            for index, qualification in enumerate(qualifications)
        ]
        print(tabulate(data, headers=header))

        qualification = self._get_item(qualifications)
        return qualification

    def get_qualification(self) -> Qualification:
        """Make qualification from AWS."""
        try:
            qualification = self._download_qualification()
        except InputError:
            logging.error('No qualification set.')
        except Exception as error:
            logging.error(error)
        else:
            return Qualification(
                name=qualification['Name'],
                description=qualification['Description'],
                identifier=qualification['QualificationTypeId'],
                status=qualification['QualificationTypeStatus'],
            )

    def create_qualification(
            self,
            name: str,
            description: Optional[str] = '',
            status: Optional[str] = 'Active'
    ) -> Qualification:
        """Create a qualification on MTurk."""
        if not description:
            description = (
                "This qualification was assigned to you based"
                " on your participation history."
                " Do not request this qualification type."
            )

        with self._client as client:
            try:
                response = client.create_qualification_type(
                    Name=name,
                    Description=description,
                    QualificationTypeStatus=status,
                )
            except Exception as error:
                logging.error(error)
            else:
                qualification = response['QualificationType']
                logger.info('Qualification created.')

                return Qualification(
                    name=qualification['Name'],
                    description=qualification['Description'],
                    identifier=qualification['QualificationTypeId'],
                    status=qualification['QualificationTypeStatus'],
                )

    def delete_qualification(self):
        """Delete qualification."""
        qualification = self.get_qualification()

        with self._client as client:
            try:
                client.delete_qualification_type(
                    QualificationTypeId=qualification.identifier
                )
            except Exception as error:
                logging.error(error)
            else:
                logger.info('Qualification deleted.')
