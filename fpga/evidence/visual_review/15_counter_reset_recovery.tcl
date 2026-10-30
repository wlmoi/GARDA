if {[catch {
puts "DISPLAYED [gtkwave::getDisplayedSignals]"
if {[llength [gtkwave::getDisplayedSignals]] != 13} {error "Not all requested signals are displayed"}
gtkwave::setZoomRangeTimes 64363190999 64369190999
gtkwave::setMarker 64366190999
gtkwave::/File/Grab_To_File {D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/visual_review/15_counter_reset_recovery.png}
gtkwave::/File/Quit
} capture_error]} {
puts stderr $capture_error
exit 1
}
