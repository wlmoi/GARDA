if {[catch {
if {[llength [gtkwave::getDisplayedSignals]] != 12} {error "Missing displayed trace"}
gtkwave::setZoomRangeTimes 1689510000 1689790000
gtkwave::setMarker 1689610001
gtkwave::setNamedMarker A 1689610000 "ALL_8_UPDATE"
gtkwave::nop
gtkwave::nop
puts "DISPLAYED [gtkwave::getDisplayedSignals]"
puts "VALUE 0 [gtkwave::getTraceValueAtMarkerFromIndex 0]"
puts "VALUE 1 [gtkwave::getTraceValueAtMarkerFromIndex 1]"
puts "VALUE 2 [gtkwave::getTraceValueAtMarkerFromIndex 2]"
puts "VALUE 3 [gtkwave::getTraceValueAtMarkerFromIndex 3]"
puts "VALUE 4 [gtkwave::getTraceValueAtMarkerFromIndex 4]"
puts "VALUE 5 [gtkwave::getTraceValueAtMarkerFromIndex 5]"
puts "VALUE 6 [gtkwave::getTraceValueAtMarkerFromIndex 6]"
puts "VALUE 7 [gtkwave::getTraceValueAtMarkerFromIndex 7]"
puts "VALUE 8 [gtkwave::getTraceValueAtMarkerFromIndex 8]"
puts "VALUE 9 [gtkwave::getTraceValueAtMarkerFromIndex 9]"
puts "VALUE 10 [gtkwave::getTraceValueAtMarkerFromIndex 10]"
puts "VALUE 11 [gtkwave::getTraceValueAtMarkerFromIndex 11]"
gtkwave::nop
gtkwave::/File/Grab_To_File {D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/parallel8_wave_proof/images/08_eight_lanes.png}
gtkwave::/File/Quit
} err]} {puts stderr $err; exit 1}
