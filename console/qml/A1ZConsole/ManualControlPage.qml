pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

Item {
    id: root
    objectName: "manualControlPage"

    required property var theme
    required property var controller
    property string currentSection: "movement"
    property real motionSpeed: 0.5
    property real jointStepDeg: 2.0
    property real linearStepMm: 10.0
    property real angularStepDeg: 5.0
    property string frameMode: "base"
    readonly property bool armDraftPending: armPage.hasPendingDrafts
    readonly property bool gripperDraftPending: gripperPage.hasPendingDrafts
    readonly property bool hasPendingDrafts:
        root.armDraftPending || root.gripperDraftPending
    readonly property bool movementVisible: root.currentSection === "movement"

    signal sectionRequested(string section)

    ColumnLayout {
        anchors.fill: parent
        spacing: root.theme.spacingS

        GlassCard {
            Layout.fillWidth: true
            Layout.preferredHeight: 76
            theme: root.theme

            RowLayout {
                anchors.fill: parent
                spacing: root.theme.spacingS

                Text {
                    Layout.fillWidth: true
                    text: qsTr("手动操控")
                    color: root.theme.text
                    font.family: root.theme.fontFamily
                    font.pixelSize: root.theme.typeTitle
                    font.weight: Font.DemiBold
                }

                AppButton {
                    objectName: "manualMovementSectionButton"
                    theme: root.theme
                    kind: root.movementVisible ? "selected" : "secondary"
                    text: qsTr("运动与定位")
                    Accessible.role: Accessible.PageTab
                    Accessible.checked: root.movementVisible
                    onClicked: root.sectionRequested("movement")
                }

                AppButton {
                    objectName: "manualToolSectionButton"
                    theme: root.theme
                    kind: !root.movementVisible ? "selected" : "secondary"
                    text: qsTr("末端工具")
                    Accessible.role: Accessible.PageTab
                    Accessible.checked: !root.movementVisible
                    onClicked: root.sectionRequested("tool")
                }
            }
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: root.movementVisible ? 0 : 1

            ArmControlPage {
                id: armPage

                theme: root.theme
                controller: root.controller
                motionSpeed: root.motionSpeed
                jointStepDeg: root.jointStepDeg
                linearStepMm: root.linearStepMm
                angularStepDeg: root.angularStepDeg
                frameMode: root.frameMode
            }

            GripperControlPage {
                id: gripperPage

                theme: root.theme
                controller: root.controller
            }
        }
    }
}
