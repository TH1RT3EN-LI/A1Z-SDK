pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

GlassCard {
    id: root

    required property var controller
    property real motionSpeed: 0.5
    property real linearStepMm: 10.0
    property string frameMode: "base"
    property bool armDraftPending: false

    implicitHeight: 320

    ColumnLayout {
        anchors.fill: parent
        spacing: 9

        SectionHeader {
            Layout.fillWidth: true
            theme: root.theme
            title: root.frameMode === "tool"
                   ? qsTr("Tool 平移") : qsTr("Base 平移")
        }

        GridLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            columns: 3
            columnSpacing: 8
            rowSpacing: 8

            Item { Layout.fillWidth: true; Layout.fillHeight: true }
            AppButton {
                Layout.fillWidth: true
                Layout.fillHeight: true
                theme: root.theme
                text: qsTr("+X")
                enabled: root.controller.motionEnabled && !root.armDraftPending
                onClicked: root.controller.jogCartesian(
                               "translation", "x",
                               root.linearStepMm / 1000.0,
                               root.frameMode, root.motionSpeed)
            }
            Item { Layout.fillWidth: true; Layout.fillHeight: true }

            AppButton {
                Layout.fillWidth: true
                Layout.fillHeight: true
                theme: root.theme
                text: qsTr("+Y")
                enabled: root.controller.motionEnabled && !root.armDraftPending
                onClicked: root.controller.jogCartesian(
                               "translation", "y",
                               root.linearStepMm / 1000.0,
                               root.frameMode, root.motionSpeed)
            }
            AppButton {
                Layout.fillWidth: true
                Layout.fillHeight: true
                theme: root.theme
                text: qsTr("+Z")
                enabled: root.controller.motionEnabled && !root.armDraftPending
                onClicked: root.controller.jogCartesian(
                               "translation", "z",
                               root.linearStepMm / 1000.0,
                               root.frameMode, root.motionSpeed)
            }
            AppButton {
                Layout.fillWidth: true
                Layout.fillHeight: true
                theme: root.theme
                text: qsTr("−Y")
                enabled: root.controller.motionEnabled && !root.armDraftPending
                onClicked: root.controller.jogCartesian(
                               "translation", "y",
                               -root.linearStepMm / 1000.0,
                               root.frameMode, root.motionSpeed)
            }

            Item { Layout.fillWidth: true; Layout.fillHeight: true }
            AppButton {
                Layout.fillWidth: true
                Layout.fillHeight: true
                theme: root.theme
                text: qsTr("−X")
                enabled: root.controller.motionEnabled && !root.armDraftPending
                onClicked: root.controller.jogCartesian(
                               "translation", "x",
                               -root.linearStepMm / 1000.0,
                               root.frameMode, root.motionSpeed)
            }
            Item { Layout.fillWidth: true; Layout.fillHeight: true }

            Item { Layout.fillWidth: true; Layout.fillHeight: true }
            AppButton {
                Layout.fillWidth: true
                Layout.fillHeight: true
                theme: root.theme
                text: qsTr("−Z")
                enabled: root.controller.motionEnabled && !root.armDraftPending
                onClicked: root.controller.jogCartesian(
                               "translation", "z",
                               -root.linearStepMm / 1000.0,
                               root.frameMode, root.motionSpeed)
            }
            Item { Layout.fillWidth: true; Layout.fillHeight: true }
        }
    }
}
