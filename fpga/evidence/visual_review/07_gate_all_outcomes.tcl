if {[catch {
puts "DISPLAYED [gtkwave::getDisplayedSignals]"
if {[llength [gtkwave::getDisplayedSignals]] != 5} {error "Not all requested signals are displayed"}
gtkwave::setZoomRangeTimes 0 11999
gtkwave::setMarker 11999
gtkwave::setNamedMarker A 999 "PASS"
gtkwave::setNamedMarker B 10999 "ABS_LIMIT"
gtkwave::setNamedMarker C 11999 "DELTA_LIMIT"
gtkwave::/File/Grab_To_File {D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/visual_review/07_gate_all_outcomes.png}
gtkwave::/File/Quit
} capture_error]} {
puts stderr $capture_error
exit 1
}
