from django.contrib import admin

from .models import Liste, Stadtteil, Strasse, Hausnummer
admin.site.register(Liste)

class HausnummerInline(admin.TabularInline):
	model = Hausnummer
	extra = 5

class HausnummerAdmin(admin.ModelAdmin):
	list_filter = ['strasse__stadtteil']
	search_fields = ['strasse__name', 'nummer']

class StrasseInline(admin.TabularInline):
	model = Strasse
	extra = 3

class StrasseAdmin(admin.ModelAdmin):
	fieldsets = [
		(None, {'fields': ['name','stadtteil']})
	]
	list_filter = ['stadtteil']
	search_fields = ['name']
	list_display = ['name','hausnummern_count','stadtteil']
	inlines = [HausnummerInline]

class StadtteilAdmin(admin.ModelAdmin):
	fieldsets = [
		(None, {'fields': ['name']})
	]
	list_display = ['name', 'hausnummern_count']
	inlines = [StrasseInline]

admin.site.register(Stadtteil, StadtteilAdmin)
admin.site.register(Strasse, StrasseAdmin)
#admin.site.register(Strasse)
admin.site.register(Hausnummer, HausnummerAdmin)
