if {[catch {
puts "DISPLAYED [gtkwave::getDisplayedSignals]"
if {[llength [gtkwave::getDisplayedSignals]] != 13} {error "Not all requested signals are displayed"}
gtkwave::setZoomRangeTimes 2955070999 2961070999
gtkwave::setMarker 2958070999
gtkwave::/File/Grab_To_File {D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/visual_review/09_policy_crc_reject.png}
gtkwave::/File/Quit
} capture_error]} {
puts stderr $capture_error
exit 1
}
