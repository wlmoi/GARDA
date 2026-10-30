if {[catch {
if {[llength [gtkwave::getDisplayedSignals]] != 10} {error "Missing displayed trace"}
gtkwave::setZoomRangeTimes 180000 11280000
gtkwave::setMarker 10540000
gtkwave::setNamedMarker A 820000 "START=0"
gtkwave::setNamedMarker B 1900000 "D0=0"
gtkwave::setNamedMarker C 2980000 "D1=1"
gtkwave::setNamedMarker D 4060000 "D2=0"
gtkwave::setNamedMarker E 5140000 "D3=1"
gtkwave::setNamedMarker F 6220000 "D4=1"
gtkwave::setNamedMarker G 7300000 "D5=0"
gtkwave::setNamedMarker H 8380000 "D6=1"
gtkwave::setNamedMarker I 9460000 "D7=0"
gtkwave::setNamedMarker J 10540000 "STOP=1"
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
gtkwave::nop
gtkwave::/File/Grab_To_File {D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/parallel8_wave_proof/images/02_rx_exact_bits.png}
gtkwave::/File/Quit
} err]} {puts stderr $err; exit 1}
