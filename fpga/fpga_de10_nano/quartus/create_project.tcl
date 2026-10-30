load_package project
if {![project_exists garda]} {project_new garda -revision garda} else {project_open garda}
source garda.qsf
export_assignments
project_close
