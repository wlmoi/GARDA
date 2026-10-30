if {[catch {
puts "DISPLAYED [gtkwave::getDisplayedSignals]"
if {[llength [gtkwave::getDisplayedSignals]] != 12} {error "Not all requested signals are displayed"}
gtkwave::setZoomRangeTimes 3904131000 3904451000
gtkwave::setMarker 3904291000
gtkwave::/File/Grab_To_File {D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/visual_review/03_planner_deadline.png}
gtkwave::/File/Quit
} capture_error]} {
puts stderr $capture_error
exit 1
}
