if {[catch {
puts "DISPLAYED [gtkwave::getDisplayedSignals]"
if {[llength [gtkwave::getDisplayedSignals]] != 13} {error "Not all requested signals are displayed"}
gtkwave::setZoomRangeTimes 3491690999 3497690999
gtkwave::setMarker 3494690999
gtkwave::/File/Grab_To_File {D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/visual_review/10_policy_estop_inference.png}
gtkwave::/File/Quit
} capture_error]} {
puts stderr $capture_error
exit 1
}
