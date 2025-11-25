# management/commands/seed_phil_loc.py
from django.core.management.base import BaseCommand
from django.db import transaction

from phil_loc.models import Region as PhilRegion, Province as PhilProvince, Municipality as PhilMunicipality, Barangay as PhilBarangay
from clientside.models import Region, Province, Municipality, Barangay


class Command(BaseCommand):
    help = "Seed custom location models using phil_loc without preserving IDs (Option B)."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Starting phil_loc → custom models sync..."))

        # --- Regions ---
        self.stdout.write("Seeding Regions...")
        region_map = {}
        for r in PhilRegion.objects.all():
            obj, _ = Region.objects.get_or_create(name=r.name)
            region_map[r.reg_code] = obj

        # --- Provinces ---
        self.stdout.write("Seeding Provinces...")
        province_map = {}
        for p in PhilProvince.objects.all():
            parent_region = region_map.get(p.reg_code)
            obj, _ = Province.objects.get_or_create(name=p.name, region=parent_region)
            province_map[p.prov_code] = obj

        # --- Municipalities ---
        self.stdout.write("Seeding Municipalities...")
        municipality_map = {}
        for m in PhilMunicipality.objects.all():
            parent_province = province_map.get(m.prov_code)
            obj, _ = Municipality.objects.get_or_create(name=m.name, province=parent_province)
            municipality_map[m.city_mun_code] = obj

        # --- Barangays ---
        self.stdout.write("Seeding Barangays...")
        for b in PhilBarangay.objects.all():
            parent_muni = municipality_map.get(b.city_mun_code)
            Barangay.objects.get_or_create(name=b.name, municipality=parent_muni)

        self.stdout.write(self.style.SUCCESS("Seeding complete. IDs auto-generated safely."))
