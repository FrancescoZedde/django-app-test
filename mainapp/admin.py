from django.contrib import admin

# Register your models here.
from mainapp.models import InventoryItem, Variant

admin.site.register(InventoryItem)
admin.site.register(Variant)