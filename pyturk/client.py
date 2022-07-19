import logging
from typing import Optional

import boto3

from mypy_boto3_mturk import MTurkClient as MTurkClientType
from pyturk.constants import PRODUCTION_HOST, SANDBOX_HOST

logger = logging.getLogger()
logger.addHandler(logging.NullHandler())


class MTurkClient:
    """A wrapper for the MTurk client."""
    def __init__(self, sandbox: bool = True) -> None:
        self.sandbox = sandbox
        self.endpoint: str = SANDBOX_HOST if sandbox else PRODUCTION_HOST
        self.client: Optional[MTurkClientType] = None

    def __enter__(self):
        try:
            self.client: MTurkClientType = boto3.client(
                'mturk',
                endpoint_url=self.endpoint,
                region_name='us-east-1',
            )
        except Exception as error:
            logging.error(f"{error}")
        else:
            logger.info(f'Connected to {self.client.meta.endpoint_url}')
            self._show_balance()
            return self.client

    def __exit__(self, exc_type, exc_value, exc_traceback) -> None:
        self.client = None

    def __repr__(self) -> str:
        return f'{type(self).__name__}(sandbox={self.sandbox!r})'

    def _show_balance(self) -> None:
        current_balance = self.client.get_account_balance()['AvailableBalance']
        logger.info(f'The current account balance is {current_balance} USD')
