if {[catch {
if {[llength [gtkwave::getDisplayedSignals]] != 4} {error "Missing displayed trace"}
gtkwave::setZoomRangeTimes 0 4000
gtkwave::setMarker 2500
gtkwave::nop
gtkwave::nop
puts "DISPLAYED [gtkwave::getDisplayedSignals]"
puts "VALUE 0 [gtkwave::getTraceValueAtMarkerFromIndex 0]"
puts "VALUE 1 [gtkwave::getTraceValueAtMarkerFromIndex 1]"
puts "VALUE 2 [gtkwave::getTraceValueAtMarkerFromIndex 2]"
puts "VALUE 3 [gtkwave::getTraceValueAtMarkerFromIndex 3]"
gtkwave::nop
gtkwave::/File/Grab_To_File {D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/parallel8_wave_proof/images/18_activation_edges.png}
gtkwave::/File/Quit
} err]} {puts stderr $err; exit 1}
