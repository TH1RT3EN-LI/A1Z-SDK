pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

GlassCard {
    id: root

    required property var controller
    property real motionSpeed: 0.5
    property real angularStepDeg: 5.0
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
                   ? qsTr("Tool 旋转") : qsTr("Base 旋转")
        }

        Repeater {
            model: [
                { axis: "x" },
                { axis: "y" },
                { axis: "z" }
            ]

            RowLayout {
                id: rotationRow

                required property var modelData
                readonly property string axisLabel:
                    rotationRow.modelData.axis === "x" ? qsTr("Roll")
                    : rotationRow.modelData.axis === "y" ? qsTr("Pitch")
                    : qsTr("Yaw")

                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 8

                Text {
                    Layout.preferredWidth: 54
                    text: rotationRow.axisLabel
                    color: root.theme.secondaryText
                    font.family: root.theme.fontFamily
                    font.pixelSize: root.theme.typeLabel
                    font.weight: Font.DemiBold
                }
                AppButton {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    theme: root.theme
                    text: qsTr("− %1°").arg(root.angularStepDeg.toFixed(1))
                    enabled: root.controller.motionEnabled
                             && !root.armDraftPending
                    onClicked: root.controller.jogCartesian(
                                   "rotation", rotationRow.modelData.axis,
                                   -root.angularStepDeg,
                                   root.frameMode, root.motionSpeed)
                }
                AppButton {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    theme: root.theme
                    text: qsTr("+ %1°").arg(root.angularStepDeg.toFixed(1))
                    enabled: root.controller.motionEnabled
                             && !root.armDraftPending
                    onClicked: root.controller.jogCartesian(
                                   "rotation", rotationRow.modelData.axis,
                                   root.angularStepDeg,
                                   root.frameMode, root.motionSpeed)
                }
            }
        }
    }
}
