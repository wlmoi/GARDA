if {[catch {
if {[llength [gtkwave::getDisplayedSignals]] != 7} {error "Missing displayed trace"}
gtkwave::setZoomRangeTimes 1827850000 1838930000
gtkwave::setMarker 1838190000
gtkwave::setNamedMarker A 1828470000 "START=0"
gtkwave::setNamedMarker B 1829550000 "D0=0"
gtkwave::setNamedMarker C 1830630000 "D1=1"
gtkwave::setNamedMarker D 1831710000 "D2=0"
gtkwave::setNamedMarker E 1832790000 "D3=1"
gtkwave::setNamedMarker F 1833870000 "D4=1"
gtkwave::setNamedMarker G 1834950000 "D5=0"
gtkwave::setNamedMarker H 1836030000 "D6=1"
gtkwave::setNamedMarker I 1837110000 "D7=0"
gtkwave::setNamedMarker J 1838190000 "STOP=1"
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
gtkwave::nop
gtkwave::/File/Grab_To_File {D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/parallel8_wave_proof/images/13_tx_exact_bits.png}
gtkwave::/File/Quit
} err]} {puts stderr $err; exit 1}
