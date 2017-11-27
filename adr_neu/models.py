from django.db import models
import csv, codecs

class Liste(models.Model):
	name = models.CharField(max_length=30, primary_key=True)
	import_file = models.FileField(blank=True, null=True)
	def __str__(self):
		return self.name
	def save(self, *args, **kwargs):
		if (self.import_file.name==None):
			super(Liste, self).save(*args, **kwargs)
		else:
			print ("import file uploaded", self.import_file.name)
			for l in self.import_file:
				(stadtteil, strasse, nummer, laenge, breite) = codecs.decode(l).strip().split(";")
				(stadtteil_o, created) = self.stadtteile.get_or_create(name=stadtteil, liste=self)
				if created:
					print (stadtteil, "created")
				(strasse_o, created) = stadtteil_o.strassen.get_or_create(name=strasse, stadtteil=stadtteil_o)
				if created:
					print (strasse, "created")
				(nummer_o, created) = strasse_o.nummern.get_or_create(nummer=nummer, 
				  defaults={'laenge': laenge, 'breite': breite})
				if not created:
					nummer_o.laenge = laenge
					nummer_o.breite = breite
					nummer_o.save()

class Stadtteil(models.Model):
	name = models.CharField(max_length=30, primary_key=True)
	liste = models.ForeignKey(Liste, related_name='stadtteile')
	def __str__(self):
		return self.name

class Strasse(models.Model):
	name = models.CharField(max_length=100)
	# Nicht 100%ig richtig, eine Strasse kann in mehreren Stadtteilen sein,
	# aber nachdem ein ManyToMany-Feld im Admin-Frontend Muehe macht, ist das
	# bisschen Redundanz hier ok
	stadtteil = models.ForeignKey(Stadtteil, related_name='strassen')
	def __str__(self):
		return self.name
	def hausnummern(self):
		return len(self.nummern.all())

class Hausnummer(models.Model):
	nummer = models.CharField(max_length=10)
	strasse = models.ForeignKey(Strasse, related_name='nummern')
	laenge = models.FloatField()
	breite = models.FloatField()
	STATUS_UNBEKANNT = ""
	STATUS_ERLEDIGT = "ERL"
	STATUS_FEHLT = "FEHLT"
	STATUS_VORHANDEN = "VORH"
	STATUS_POS_DIFF = "POS"
	STATUS_OSM_VERT = "OSM_VERT"
	status = models.CharField(
		max_length=8,
		default=STATUS_UNBEKANNT,
		choices = (
			(STATUS_UNBEKANNT, "??"),
			(STATUS_FEHLT, "fehlt in OSM"),
			(STATUS_VORHANDEN, "in OSM vorhanden"),
			(STATUS_ERLEDIGT, "erledigt"),
			(STATUS_POS_DIFF, "Position abweichend"),
			(STATUS_OSM_VERT, "OSM-Inkonsistenz: Objekte verstreut"),
		)
	)
	
	def __str__(self):
		return str(self.strasse)+" "+self.nummer
