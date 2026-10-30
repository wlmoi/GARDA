if {[catch {
puts "DISPLAYED [gtkwave::getDisplayedSignals]"
if {[llength [gtkwave::getDisplayedSignals]] != 13} {error "Not all requested signals are displayed"}
gtkwave::setZoomRangeTimes 62511330999 62517330999
gtkwave::setMarker 62514330999
gtkwave::/File/Grab_To_File {D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/visual_review/13_counter_accepted_max.png}
gtkwave::/File/Quit
} capture_error]} {
puts stderr $capture_error
exit 1
}
