"""Patient: sign in with an ID, or register a new patient."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from ...api import Patient
from ..state import AppState
from ..tasks import run_async
from ..widgets import (
    Avatar,
    Banner,
    Card,
    Page,
    PageHeader,
    TextField,
    button,
    clear_layout,
    label,
    scrollable,
)


class PatientsPage(Page):
    signedIn = Signal(object)  # Patient

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self._registered: Patient | None = None

        content = QWidget()
        content.setObjectName("Page")
        column = QVBoxLayout(content)
        column.setContentsMargins(36, 30, 36, 36)
        column.setSpacing(20)

        column.addWidget(PageHeader(
            "Patient",
            "Sign in with a patient ID, or register someone new.",
            eyebrow="Account",
        ))

        self.notice = Banner("", "info")
        self.notice.setVisible(False)
        column.addWidget(self.notice)

        self.error = Banner("", "danger")
        self.error.setVisible(False)
        column.addWidget(self.error)

        self.current_box = QVBoxLayout()
        column.addLayout(self.current_box)

        row = QHBoxLayout()
        row.setSpacing(20)
        row.addWidget(self._build_sign_in(), 1)
        row.addWidget(self._build_register(), 1)
        column.addLayout(row)
        column.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrollable(content))

        state.patientChanged.connect(lambda _p: self._render_current())
        self._render_current()

    # -- construction ------------------------------------------------------------------

    def _build_sign_in(self) -> Card:
        card = Card(padding=24, spacing=14)
        card.body.addWidget(label("Sign in", "h2"))
        card.body.addWidget(label("Use the ID the patient received when they registered.", "muted", wrap=True))

        self.id_field = TextField(
            "Patient ID", placeholder="e.g. 12", digits_only=True, max_length=9,
        )
        self.id_field.returnPressed.connect(self._sign_in)
        card.body.addWidget(self.id_field)

        self.sign_in_button = button("Sign in", "primary", icon="log-in", size="lg")
        self.sign_in_button.clicked.connect(self._sign_in)
        card.body.addWidget(self.sign_in_button)
        card.body.addStretch(1)
        return card

    def _build_register(self) -> Card:
        card = Card(padding=24, spacing=14)
        self.register_box = card.body

        self.register_form = QWidget()
        form = QVBoxLayout(self.register_form)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(14)
        form.addWidget(label("Register a new patient", "h2"))
        form.addWidget(label("Only a name is needed. You will be given an ID to sign in with.", "muted", wrap=True))

        self.first_field = TextField("First name", placeholder="First name")
        self.last_field = TextField("Last name", placeholder="Last name (optional)")
        self.last_field.returnPressed.connect(self._register)
        self.first_field.returnPressed.connect(self.last_field.focus)
        form.addWidget(self.first_field)
        form.addWidget(self.last_field)

        self.register_button = button("Register patient", icon="user-plus", size="lg")
        self.register_button.clicked.connect(self._register)
        form.addWidget(self.register_button)
        card.body.addWidget(self.register_form)

        self.receipt = QWidget()
        self.receipt.setVisible(False)
        card.body.addWidget(self.receipt)
        return card

    # -- current patient --------------------------------------------------------------------

    def _render_current(self) -> None:
        clear_layout(self.current_box)
        patient = self.state.patient
        if patient is None:
            return

        card = Card(padding=18, spacing=0)
        row = QHBoxLayout()
        row.setSpacing(14)
        row.addWidget(Avatar(patient.display_name, 48))
        names = QVBoxLayout()
        names.setSpacing(2)
        names.addWidget(label(f"Signed in as {patient.display_name}", "h2"))
        names.addWidget(label(f"Patient ID {patient.id}", "muted"))
        row.addLayout(names, 1)
        out = button("Sign out", icon="log-out")
        out.clicked.connect(lambda: self.state.set_patient(None))
        row.addWidget(out)
        card.body.addLayout(row)
        self.current_box.addWidget(card)

    def set_notice(self, text: str | None) -> None:
        """A message explaining why the user was sent here (e.g. before an exercise)."""
        self.notice.set(text or "", "info")
        self.notice.setVisible(bool(text))

    def on_show(self) -> None:
        self.error.setVisible(False)
        self.id_field.focus()

    # -- actions ---------------------------------------------------------------------------------

    def _show_error(self, message: str) -> None:
        self.error.set(message, "danger")
        self.error.setVisible(True)

    def _busy(self, button_widget, busy: bool, idle_text: str) -> None:
        button_widget.setEnabled(not busy)
        button_widget.setText("Working..." if busy else idle_text)

    def _sign_in(self) -> None:
        self.error.setVisible(False)
        text = self.id_field.text()
        if not text:
            self.id_field.set_error("Enter a numeric patient ID")
            return

        patient_id = int(text)
        client = self.state.client
        self._busy(self.sign_in_button, True, "Sign in")

        def done(patient: Patient | None) -> None:
            self._busy(self.sign_in_button, False, "Sign in")
            if patient is None:
                self.id_field.set_error(f"No patient with ID {patient_id}")
                return
            self.id_field.setText("")
            self.state.set_patient(patient)
            self.signedIn.emit(patient)

        def failed(exc: Exception) -> None:
            self._busy(self.sign_in_button, False, "Sign in")
            self._show_error(str(exc))

        run_async(lambda: client.get_patient(patient_id), done, failed, owner=self)

    def _register(self) -> None:
        self.error.setVisible(False)
        first, last = self.first_field.text(), self.last_field.text()
        if not first:
            self.first_field.set_error("First name is required")
            return

        client = self.state.client
        self._busy(self.register_button, True, "Register patient")

        def done(patient: Patient) -> None:
            self._busy(self.register_button, False, "Register patient")
            self._show_receipt(patient)

        def failed(exc: Exception) -> None:
            self._busy(self.register_button, False, "Register patient")
            self._show_error(str(exc))

        run_async(lambda: client.create_patient(first, last or first), done, failed, owner=self)

    def _show_receipt(self, patient: Patient) -> None:
        """After registering, show the ID prominently: it is the only way back in."""
        self._registered = patient
        self.register_form.setVisible(False)

        receipt = QWidget()
        column = QVBoxLayout(receipt)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(12)
        column.addWidget(Banner("Registration complete.", "success"))
        column.addWidget(label(patient.display_name, "h2"))
        column.addWidget(label("Patient ID", "caption"))
        column.addWidget(label(str(patient.id), "display"))
        column.addWidget(label("Write this number down - you will need it to sign in next time.", "muted", wrap=True))

        go = button("Continue", "primary", icon="arrow-right", size="lg")
        go.clicked.connect(self._continue_after_registration)
        column.addWidget(go)

        old = self.receipt
        self.register_box.replaceWidget(old, receipt)
        old.deleteLater()
        receipt.show()  # a widget added to an already-visible layout starts hidden
        self.receipt = receipt

    def _continue_after_registration(self) -> None:
        patient = self._registered
        if patient is None:
            return
        # Reset the form for the next registration.
        self.first_field.setText("")
        self.last_field.setText("")
        self.receipt.setVisible(False)
        self.register_form.setVisible(True)
        self._registered = None

        self.state.set_patient(patient)
        self.signedIn.emit(patient)
