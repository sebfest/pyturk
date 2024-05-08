import csv

from typing import List

from .models import Assignment
from .exceptions import MissingField, MissingHeader


def read_bonus_data(file_path: str) -> List[Assignment]:
    """Read bonus data from file"""

    VALID_HEADERS = [
        'AssignmentId',
        'WorkerId',
        'BonusAmount',
        'Reason',
    ]

    def get_missing_field(data_row):
        return [field for field in VALID_HEADERS if not data_row.get(field)]

    with open(file_path, encoding='utf-8-sig') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        csv_headers = csv_reader.fieldnames

        if not all(header in csv_headers for header in VALID_HEADERS):
            print(csv_headers)
            difference = list(set(VALID_HEADERS) - set(csv_headers))
            raise MissingHeader(f'Missing column: {", ".join(difference)}')

        assignment_list = []
        for row in csv_reader:
            if all([row.get(col) for col in VALID_HEADERS]):
                assignment_list.append(Assignment.from_dict(row))
            else:
                missing = get_missing_field(row)
                raise MissingField(f'Fields missing: {missing}')

    return assignment_list



