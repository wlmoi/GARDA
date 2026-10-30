if {[catch {
if {[llength [gtkwave::getDisplayedSignals]] != 12} {error "Missing displayed trace"}
gtkwave::setZoomRangeTimes 1827710000 1827990000
gtkwave::setMarker 1827890001
gtkwave::setNamedMarker A 1827810000 "CORE_DONE"
gtkwave::setNamedMarker B 1827890000 "RESULT_VALID"
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
gtkwave::/File/Grab_To_File {D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/parallel8_wave_proof/images/11_capture_q88.png}
gtkwave::/File/Quit
} err]} {puts stderr $err; exit 1}
