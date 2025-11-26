from django.core.management.base import BaseCommand
from clientside.models import Operator, NumberOperatorIdentifier


class Command(BaseCommand):
    help = "Populate Operator and NumberOperatorIdentifier tables"

    def handle(self, *args, **kwargs):
        data = {
            "Globe Telecom / TM": [
                817, 905, 906, 915, 916, 917, 926, 926, 927,
                935, 936, 945, 953, 955, 956, 956, 965, 966, 967,
                975, 977, 995, 997
            ],
            "ABS-CBN Mobile": [937],
            "Globe Telecom / GOMO / TM": [976],
            "Cherry Prepaid": [996],
            "Globe Postpaid": [
                9175, 9176, 9178,
                9253, 9255, 9256, 9257, 9258
            ],
            "Smart / TNT": [
                813, 907, 908, 909, 910, 811,
                912, 913, 914, 918, 919, 920, 921,
                928, 929, 930, 938, 939, 940, 946,
                947, 948, 949, 950, 951, 961,
                963, 968, 969, 970, 981, 989, 992,
                998, 999
            ],
            "DITO SIM": [
                895, 896, 897, 898,
                991, 992, 993, 994
            ],
            "Sun Cellular": [
                922, 923, 924, 925,
                931, 932, 933, 934,
                941, 942, 943, 944
            ],
        }

        for operator_name, numbers in data.items():
            operator, created = Operator.objects.get_or_create(name=operator_name)

            for num in numbers:
                NumberOperatorIdentifier.objects.get_or_create(
                    number=num,
                    operator=operator
                )

        self.stdout.write(self.style.SUCCESS("Operators & number identifiers populated successfully!"))
