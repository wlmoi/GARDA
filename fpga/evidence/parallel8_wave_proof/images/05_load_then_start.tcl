if {[catch {
if {[llength [gtkwave::getDisplayedSignals]] != 9} {error "Missing displayed trace"}
gtkwave::setZoomRangeTimes 1689210000 1689670000
gtkwave::setMarker 1689489999
gtkwave::setNamedMarker A 1689470000 "START"
gtkwave::setNamedMarker B 1689490000 "BUSY"
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
gtkwave::nop
gtkwave::/File/Grab_To_File {D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/parallel8_wave_proof/images/05_load_then_start.png}
gtkwave::/File/Quit
} err]} {puts stderr $err; exit 1}
