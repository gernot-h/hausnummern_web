from django.http import HttpResponse, HttpResponseServerError, StreamingHttpResponse
from django.template import loader
from django.shortcuts import render, get_object_or_404, get_list_or_404
from adr_neu.models import Liste, Stadtteil


def show_listen(request):
	listen = Liste.objects.all()
	return render(
		request,
		'adr_neu/index.html',
		{
			'listen': listen,
		}
	)

def prepare_adressen(liste, stadtteile=None):
	adressen = [] 
	if stadtteile==None:
		stadtteile = liste.stadtteile.order_by('name').all()
	counter = 1
	for stadtteil in stadtteile:
		l = []
		for strasse in stadtteil.strassen.order_by('name').all():
			for nummer in strasse.nummern.order_by('nummer').all():
				l.append({'strasse': strasse.name, 'nummer': nummer.nummer, 
				  'laenge': nummer.laenge, 'breite': nummer.breite, 'status': nummer.get_status_display(), 'counter': counter})
				counter+=1
		adressen.append([stadtteil, l])
	return adressen

def do_overpass_update(stadtteile):
	import requests, json
	from functools import reduce
	t = loader.get_template('adr_neu/overpass-query.txt')
	for stadtteil in stadtteile:
		yield "<h3>STADTTEIL %s</h3>\n" % stadtteil.name

		l = {}
		osm_koords={}
		for strasse in stadtteil.strassen.order_by('name').all():
			for nummer in strasse.nummern.order_by('nummer').all():
				l.append({'strasse': strasse.name, 'nummer': nummer.nummer, 'obj': nummer})
		yield "Anfrage: %i Adressen<br/>\n" % len(l) 
		params = ({ "data": t.render({'adressen': l}) })
		res = requests.post("http://overpass-api.de/api/interpreter", data=params)
		try:
			res = json.loads(res.text)
		except Exception:
			yield "<p><b>FEHLER: Overpass Antwort konnte nicht verstanden werden!!</b></p>\n"
			yield "<p><tt>"
			yield from res.text
			yield "</tt></p>"
			return

		yield "Antwort: %i Einträge<b/>\n" % len(res['elements']) 
		for result in res['elements']:
			#print(result)
			if "center" in result.keys():
				osm_lat = result["center"]["lat"]
				osm_lon = result["center"]["lon"]
			else:
				osm_lat = result["lat"]
				osm_lon = result["lon"]
			osm_street = result["tags"]["addr:street"]
			osm_number = result["tags"]["addr:housenumber"]
			if (osm_street, osm_number) in osm_koords.keys():
				osm_koords[(osm_street, osm_number)].append((osm_lat, osm_lon))
				if (abs(osm_lat-osm_koords[(osm_street, osm_number)][0][0])>0.00013 or 
				    abs(osm_lon-osm_koords[(osm_street, osm_number)][0][1]>0.0002)): # ca. 15m
					yield "%s %s prüfen!<br/>" % (osm_street, osm_number)
					pass
			else:
				osm_koords[(osm_street, osm_number)]=[(osm_lat, osm_lon)]
				
		for (street, num) in osm_koords.keys():
			anzahl = len(osm_koords[(street, num)])
			if anzahl>1:
				(lat_avg, lon_avg) = reduce (lambda a,b: (a[0]+b[0], a[1]+b[1]), osm_koords[(street, num)])
				(lat_avg, lon_avg) = (lat_avg/anzahl, lon_avg/anzahl)
				osm_koords[(street, num)]=[(lat_avg, lon_avg)]
			
	yield "<h3>Update erfolgreich abgeschlossen</h3>\n"

def overpass_update(request, liste_name):
	liste = get_object_or_404(Liste, pk=liste_name)
	stadtteile = liste.stadtteile.order_by('name').all()
	return StreamingHttpResponse(do_overpass_update(stadtteile))

def show_liste(request, liste_name):
	liste = get_object_or_404(Liste, pk=liste_name)
	adressen = prepare_adressen(liste)
#	overpass_update(liste)

	return render(
		request,
		'adr_neu/show.html',
		{
			'adressen': adressen,
			'liste_name': liste_name
		}
	)

def download_liste(request, liste_name):
	liste = get_object_or_404(Liste, pk=liste_name)

	if "format" in request.GET.keys():
		get_format = request.GET["format"]
	else:
		get_format = "csv"

	if "stadtteil" in request.GET.keys():	
		get_stadtteil = request.GET["stadtteil"]
		stadtteile = get_list_or_404(Stadtteil, name=get_stadtteil)
		filename = "hausnummern-la-%s-%s.%s" % (get_stadtteil, liste_name, get_format)
	else:
		stadtteile = None
		filename = "hausnummern-la-%s.%s" % (liste_name, get_format)

	adressen = prepare_adressen(liste, stadtteile)
	
	if get_format=="csv":
		response = HttpResponse(content_type='text/csv')
		t = loader.get_template('adr_neu/csv.txt')
	elif get_format=="osm":
		response = HttpResponse(content_type='text/xml')
		t = loader.get_template('adr_neu/osm.txt')
	elif get_format=="gpx":
		response = HttpResponse(content_type='text/xml')
		t = loader.get_template('adr_neu/gpx.txt')
	response['Content-Disposition'] = 'attachment; filename="%s"' % filename
	
	response.write(t.render({
		'adressen': adressen,
	}))
	return response
