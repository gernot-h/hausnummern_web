from django.http import HttpResponse, HttpResponseServerError, StreamingHttpResponse, Http404
from django.template import loader
from django.shortcuts import render, get_object_or_404, get_list_or_404
from adr_neu.models import Stadtteil, Hausnummer


def show_stadtteile(request):
	stadtteile = Stadtteil.objects.order_by('name').all()
	return render(
		request,
		'adr_neu/index.html',
		{
			'stadtteile': stadtteile,
		}
	)

def prepare_adressen(stadtteil_name="alle", typ_filter="alle"):
	if stadtteil_name=="alle":
		stadtteile = Stadtteil.objects.order_by('name').all()
	else:
		stadtteile = [get_object_or_404(Stadtteil, pk=stadtteil_name)]
	adressen = []
	if typ_filter.startswith("todo-"):
		typ_filter = typ_filter[5:]
		ignoriere_status=(Hausnummer.STATUS_OK_AUTO, Hausnummer.STATUS_OK_MANU)
	else:
		ignoriere_status=()
		
	if typ_filter not in ("alle", Hausnummer.GIS_NEU, Hausnummer.GIS_VERSCHOBEN, Hausnummer.GIS_GELOESCHT):
		raise Http404("typ_filter %s nicht vorhanden" % typ_filter)
	for stadtteil in stadtteile:
		l = []
		for strasse in stadtteil.strassen.order_by('name').all():
			for nummer in strasse.nummern.order_by('nummer').all():
				if nummer.status in ignoriere_status:
					continue
				if typ_filter!="alle" and nummer.gis_status!=typ_filter:
					continue
				l.append({'strasse': strasse, 'nummer': nummer})
		adressen.append([stadtteil, l])
	return adressen

def do_overpass_update(stadtteile):
	import requests, json
	from functools import reduce
	t = loader.get_template('adr_neu/overpass-query.txt')
	for stadtteil in stadtteile:
		yield "<h3>STADTTEIL %s</h3>\n" % stadtteil.name

		l = {}
		for strasse in stadtteil.strassen.order_by('name').all():
			for nummer in strasse.nummern.order_by('nummer').all():
				if nummer.nummer=="":
					yield "Abfrage nach Straße ohne Nr. noch nicht implementiert: "+strasse.name+"</br>"
					continue
				l[(strasse.name, nummer.nummer)] = nummer
				if nummer.status!=Hausnummer.STATUS_OK_MANU:
					# erstmal alle als fehlend markieren
					if nummer.gis_status==Hausnummer.GIS_GELOESCHT:
						nummer.status=Hausnummer.STATUS_OK_AUTO
					else:
						nummer.status=Hausnummer.STATUS_FEHLT
					nummer.save()

		yield "Anfrage: %i Adressen<br/>\n" % len(l) 
		params = ({ "data": t.render({'adressen': l}) })
		res = requests.post("http://overpass-api.de/api/interpreter", data=params)
		res.encoding="utf-8"
		try:
			res = json.loads(res.text)
		except Exception:
			yield "<p><b>FEHLER: Overpass Antwort konnte nicht verstanden werden!!</b></p>\n"
			yield "<p><tt>"
			yield from res.text
			yield "</tt></p>"
			return

		yield "Antwort: %i Einträge<br/>\n" % len(res['elements']) 
		osm_koords={}
		for result in res['elements']:
			if "center" in result.keys():
				osm_lat = result["center"]["lat"]
				osm_lon = result["center"]["lon"]
			else:
				osm_lat = result["lat"]
				osm_lon = result["lon"]
			strasse = result["tags"]["addr:street"]
			if "addr:housenumber" not in result["tags"].keys():
				continue
			nummer = result["tags"]["addr:housenumber"]
			if (strasse, nummer) in osm_koords.keys():
				osm_koords[(strasse, nummer)].append((osm_lat, osm_lon))
				if (abs(osm_lat-osm_koords[(strasse, nummer)][0][0])>0.00013 or 
				    abs(osm_lon-osm_koords[(strasse, nummer)][0][1]>0.0002)): # ca. 15m
					yield "OSM-Inkonsistenz: verstreute Objekte für %s %s!<br/>" % (strasse, nummer)
					if l[(strasse, nummer)]!=Hausnummer.STATUS_OK_MANU:
						l[(strasse, nummer)].status=Hausnummer.STATUS_OSM_VERT
						l[(strasse, nummer)].save()
			else:
				osm_koords[(strasse, nummer)]=[(osm_lat, osm_lon)]
				
		for (strasse, nummer) in osm_koords.keys():
			if l[(strasse, nummer)].status in (Hausnummer.STATUS_OK_MANU, Hausnummer.STATUS_OSM_VERT):
				continue
			anzahl = len(osm_koords[(strasse, nummer)])
			if anzahl>1:
				(lat_avg, lon_avg) = reduce (lambda a,b: (a[0]+b[0], a[1]+b[1]), osm_koords[(strasse, nummer)])
				(lat_avg, lon_avg) = (lat_avg/anzahl, lon_avg/anzahl)
				osm_koords[(strasse, nummer)]=[(lat_avg, lon_avg)]
			if (abs(l[(strasse, nummer)].breite-osm_koords[(strasse, nummer)][0][0])>0.00013 or 
			    abs(l[(strasse, nummer)].laenge-osm_koords[(strasse, nummer)][0][1]>0.0002)): # ca. 15m
				l[(strasse, nummer)].status=Hausnummer.STATUS_POS_DIFF
			elif l[(strasse, nummer)].gis_status==Hausnummer.GIS_GELOESCHT:
				l[(strasse, nummer)].status=Hausnummer.STATUS_VORHANDEN
			else:
				l[(strasse, nummer)].status=Hausnummer.STATUS_OK_AUTO
				
			l[(strasse, nummer)].save()

	yield "<h3>Update erfolgreich abgeschlossen</h3>\n"

def overpass_update(request, stadtteil_name):
	if stadtteil_name=="alle":
		stadtteile = Stadtteil.objects.all()
	else:
		stadtteile = [get_object_or_404(Stadtteil, pk=stadtteil_name)]
	return StreamingHttpResponse(do_overpass_update(stadtteile))

def show_stadtteil(request, stadtteil_name):
	adressen = prepare_adressen(stadtteil_name)
	return render(
		request,
		'adr_neu/show.html',
		{
			'adressen': adressen,
		}
	)

def download(request, stadtteil_name):
	if "format" in request.GET.keys():
		get_format = request.GET["format"]
	else:
		get_format = "csv"

	if "typ" in request.GET.keys():	
		typ = request.GET["typ"]
	else:
		typ = "alle"
	filename = "hausnummern-la-%s-%s.%s" % (stadtteil_name, typ, get_format)

	adressen = prepare_adressen(stadtteil_name, typ)
	
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
