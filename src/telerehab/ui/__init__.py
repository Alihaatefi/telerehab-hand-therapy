"""Presentation layer, built on Qt (PySide6).

``theme``       design tokens and the application stylesheet
``icons``       vector icons and the application mark
``widgets``     the reusable building blocks every page is made from
``charts``      the progress chart and the PDF report
``art``         the exercise scene, butterfly and flower, drawn in code
``camera``      the camera on its own thread
``tasks``       blocking calls off the interface thread
``state``       who is signed in, how to reach the backend and camera
``pages``       one module per screen
``main_window`` navigation shell
``app``         start-up

Nothing here is imported by the rest of the package: the vision, exercise and
report logic knows nothing about the interface that displays it.
"""
