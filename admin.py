from ni_deeds.models import *

def register_models( admin_site ):
    for klass in (Property,):
        admin_site.register( klass, klass.customAdmin())
