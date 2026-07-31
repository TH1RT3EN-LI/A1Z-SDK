pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

GridLayout {
    id: root

    required property var theme
    required property var controller
    property real motionSpeed: 0.5
    property real linearStepMm: 10.0
    property real angularStepDeg: 5.0
    property string frameMode: "base"
    property bool armDraftPending: false

    implicitHeight: 320
    columns: 2
    columnSpacing: root.theme.spacingM
    rowSpacing: root.theme.spacingM

    CartesianTranslationPanel {
        Layout.fillWidth: true
        Layout.fillHeight: true
        theme: root.theme
        controller: root.controller
        motionSpeed: root.motionSpeed
        linearStepMm: root.linearStepMm
        frameMode: root.frameMode
        armDraftPending: root.armDraftPending
    }

    CartesianRotationPanel {
        Layout.fillWidth: true
        Layout.fillHeight: true
        theme: root.theme
        controller: root.controller
        motionSpeed: root.motionSpeed
        angularStepDeg: root.angularStepDeg
        frameMode: root.frameMode
        armDraftPending: root.armDraftPending
    }
}
