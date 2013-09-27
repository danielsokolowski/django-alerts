from django.conf.urls import patterns, url

from alerts.views import AlertUpdateView, AlertIndexView, AlertCreateView

urlpatterns = patterns('',
	# order matters - from most specific to least
	#url(r'^shipping-term-(?P<slug>[-_\w]+?)-(?P<pk>[\d]+)/$',  ShippingTermDetailView.as_view(), name='ShippingTermDetailView'),
	#url(r'^payment-term-(?P<slug>[-_\w]+?)-(?P<pk>[\d]+)/$',  PaymentTermDetailView.as_view(), name='PaymentTermDetailView'),
	url(r'^$', AlertIndexView.as_view(), name='AlertIndexView'),
	url(r'^create/$', AlertCreateView.as_view(), name='AlertCreateView'),
	url(r'^update/(?P<pk>[0-9]+)/$', AlertUpdateView.as_view(), name='AlertUpdateView'),
	 	
)