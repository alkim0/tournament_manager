from django.core.management.base import BaseCommand
from tmdb.models import School

import csv


def update_short_names(csv_path):
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            school = School.objects.get(name=row["school name"])
            school.short = row["short name"]
            school.save()


class Command(BaseCommand):
    help = 'Takes in a csv file of school names and respective short names and updates the db. The csv should have 2 fields and have a header line of the form: "school name,short name"'

    def add_arguments(self, parser):
        parser.add_argument(
            "csv-file", type=str, help="Path to csv file of schools names"
        )

    def handle(self, *args, **options):
        update_short_names(options["csv-file"])
