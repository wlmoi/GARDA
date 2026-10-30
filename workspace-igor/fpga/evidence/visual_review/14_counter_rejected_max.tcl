if {[catch {
puts "DISPLAYED [gtkwave::getDisplayedSignals]"
if {[llength [gtkwave::getDisplayedSignals]] != 13} {error "Not all requested signals are displayed"}
gtkwave::setZoomRangeTimes 63008230999 63014230999
gtkwave::setMarker 63011230999
gtkwave::/File/Grab_To_File {D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/visual_review/14_counter_rejected_max.png}
gtkwave::/File/Quit
} capture_error]} {
puts stderr $capture_error
exit 1
}
