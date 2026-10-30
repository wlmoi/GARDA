if {[catch {
puts "DISPLAYED [gtkwave::getDisplayedSignals]"
if {[llength [gtkwave::getDisplayedSignals]] != 10} {error "Not all requested signals are displayed"}
gtkwave::setZoomRangeTimes 2183414000 2185414999
gtkwave::setMarker 2185414000
gtkwave::setNamedMarker A 2185415000 "DONE_54348"
gtkwave::/File/Grab_To_File {D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/visual_review/08_policy_bit_exact_done.png}
gtkwave::/File/Quit
} capture_error]} {
puts stderr $capture_error
exit 1
}
