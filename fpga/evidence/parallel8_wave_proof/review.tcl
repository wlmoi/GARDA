if {[catch {
if {[llength [gtkwave::getDisplayedSignals]] != 12} {error "Missing displayed trace"}
gtkwave::setZoomRangeTimes 1689510000 1689790000
gtkwave::setMarker 1689610001
gtkwave::setNamedMarker A 1689610000 "ALL_8_UPDATE"
puts "DISPLAYED [gtkwave::getDisplayedSignals]"
} err]} {puts stderr $err; exit 1}
