from django.db import models
from django.core.exceptions import ValidationError
import csv, codecs


class Stadtteil(models.Model):
	name = models.CharField(max_length=30, primary_key=True)
	bearbeiter = models.CharField(max_length=30, default="", blank=True)
	class Meta:
		verbose_name_plural = "Stadtteile"
	def __str__(self):
		if self.name=="":
			return "(leer)"
		else:
			return self.name
	def hausnummern_count(self):
		return Hausnummer.objects.filter(strasse__stadtteil__name=self.name).count()
	def erledigt_prozent(self):
		nummern = Hausnummer.objects.filter(strasse__stadtteil__name=self.name)
		ok = nummern.filter(status__in=(Hausnummer.STATUS_OK_AUTO, Hausnummer.STATUS_OK_MANU))
		return (ok.count()*100 / nummern.count())

class Strasse(models.Model):
	name = models.CharField(max_length=100)
	# Nicht 100%ig richtig, eine Strasse kann in mehreren Stadtteilen sein,
	# aber nachdem ein ManyToMany-Feld im Admin-Frontend Muehe macht, ist das
	# bisschen Redundanz hier ok
	stadtteil = models.ForeignKey(Stadtteil, related_name='strassen')
	class Meta:
		verbose_name_plural = "Strassen"
	def __str__(self):
		return self.name
	def hausnummern_count(self):
		return self.nummern.all().count()

class Hausnummer(models.Model):
	nummer = models.CharField(max_length=10, blank=True)
	strasse = models.ForeignKey(Strasse, related_name='nummern')
	laenge = models.FloatField()
	breite = models.FloatField()
	STATUS_UNBEKANNT = ""
	STATUS_FEHLT = "FEHLT"
	STATUS_VORHANDEN = "VORH"
	STATUS_OK_AUTO = "OK"
	STATUS_OK_MANU = "OK_MANU"
	STATUS_POS_DIFF = "POS"
	STATUS_OSM_VERT = "OSM_VERT"
	status = models.CharField(
		max_length=8,
		default=STATUS_UNBEKANNT,
		choices = (
			(STATUS_UNBEKANNT, "??"),
			(STATUS_FEHLT, "fehlt in OSM"),
			(STATUS_VORHANDEN, "vorhanden"),
			(STATUS_OK_AUTO, "ok (autom.)"),
			(STATUS_OK_MANU, "ok (manuell)"),
			(STATUS_POS_DIFF, "Position abweichend"),
			(STATUS_OSM_VERT, "OSM-Objekte verstreut!"),
		)
	)
	kommentar = models.CharField(max_length=400, default="", blank=True)
	GIS_NEU = "NEW"
	GIS_VERSCHOBEN = "CHNG"
	GIS_GELOESCHT = "DEL"
	gis_status = models.CharField(
		max_length = 4,
		choices = (
			(GIS_NEU, "neu"),
			(GIS_VERSCHOBEN, "verschoben"),
			(GIS_GELOESCHT, "gelöscht"),
		)
	)
	class Meta:
		verbose_name_plural = "Hausnummern"
	def __str__(self):
		return str(self.strasse)+" "+self.nummer
	def clean(self):
		if self.status == Hausnummer.STATUS_OK_MANU and self.kommentar=="":
			raise ValidationError({'kommentar': 'bei OK_MANU muss ein Kommentar eingegeben werden'})

class Liste(models.Model):
	typ = models.CharField(
		max_length = 4,
		choices = (
			(Hausnummer.GIS_NEU, "Neu"),
			(Hausnummer.GIS_VERSCHOBEN, "Verschoben"),
			(Hausnummer.GIS_GELOESCHT, "Gelöscht"),
		)
	) 
	import_file = models.FileField()
	class Meta:
		verbose_name_plural = "Listen"

	def save(self, *args, **kwargs):
		print ("import file uploaded", self.import_file.name)
		for l in self.import_file:
			(stadtteil, strasse, nummer, laenge, breite) = codecs.decode(l).strip().split(";")
			(stadtteil_o, created) = Stadtteil.objects.get_or_create(name=stadtteil)
			if created:
				print (stadtteil, "created")
			(strasse_o, created) = stadtteil_o.strassen.get_or_create(name=strasse, stadtteil=stadtteil_o)
			if created:
				print (strasse, "created")
			(nummer_o, created) = strasse_o.nummern.get_or_create(nummer=nummer, 
			  defaults={'laenge': laenge, 'breite': breite, 'gis_status': self.typ })
			if not created:
				nummer_o.laenge = laenge
				nummer_o.breite = breite
				nummer_o.gis_status = self.typ
				nummer_o.save()
