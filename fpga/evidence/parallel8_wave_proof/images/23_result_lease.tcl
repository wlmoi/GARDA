if {[catch {
if {[llength [gtkwave::getDisplayedSignals]] != 15} {error "Missing displayed trace"}
gtkwave::setZoomRangeTimes 5824550000 5825350000
gtkwave::setMarker 5824950001
gtkwave::setNamedMarker A 5824950000 "ERROR_11"
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
puts "VALUE 12 [gtkwave::getTraceValueAtMarkerFromIndex 12]"
puts "VALUE 13 [gtkwave::getTraceValueAtMarkerFromIndex 13]"
puts "VALUE 14 [gtkwave::getTraceValueAtMarkerFromIndex 14]"
gtkwave::nop
gtkwave::/File/Grab_To_File {D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/parallel8_wave_proof/images/23_result_lease.png}
gtkwave::/File/Quit
} err]} {puts stderr $err; exit 1}
