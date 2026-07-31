pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

Item {
    id: root

    required property var theme
    required property var controller
    required property var jointData
    required property int jointIndex
    required property string targetText
    property real motionSpeed: 0.5
    property real jointStepDeg: 2.0
    property bool draftPending: false
    property bool draftInitialized: false
    property bool draftStale: false

    signal targetEdited(string value)

    implicitHeight: 44

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 1
        visible: root.jointIndex < 5
        color: root.theme.separator
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 10
        anchors.rightMargin: 10
        spacing: 7

        Text {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            text: root.jointData.name
            color: root.theme.text
            horizontalAlignment: Text.AlignHCenter
            font.family: root.theme.fontFamily
            font.pixelSize: root.theme.typeLabel
            font.weight: Font.Bold
        }
        Text {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            text: Number(root.jointData.position).toFixed(2) + "°"
            color: root.theme.text
            horizontalAlignment: Text.AlignHCenter
            font.family: "monospace"
            font.pixelSize: root.theme.typeLabel
        }
        Text {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            text: "[" + Number(root.jointData.minimum).toFixed(0)
                  + ", " + Number(root.jointData.maximum).toFixed(0) + "]"
            color: root.theme.tertiaryText
            horizontalAlignment: Text.AlignHCenter
            font.family: "monospace"
            font.pixelSize: root.theme.typeCaption
        }
        AppButton {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            theme: root.theme
            text: qsTr("− %1°").arg(root.jointStepDeg.toFixed(1))
            enabled: root.controller.motionEnabled && !root.draftPending
            onClicked: root.controller.jogJoint(
                           root.jointIndex,
                           -root.jointStepDeg,
                           root.motionSpeed)
        }
        AppTextField {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            theme: root.theme
            enabled: root.controller.motionEnabled
                     && root.draftInitialized
                     && !root.draftStale
            text: root.targetText
            horizontalAlignment: Text.AlignHCenter
            validator: DoubleValidator {
                bottom: Number(root.jointData.minimum)
                top: Number(root.jointData.maximum)
                decimals: 3
                notation: DoubleValidator.StandardNotation
            }
            Accessible.name: qsTr("%1 目标角度").arg(root.jointData.name)
            onTextEdited: root.targetEdited(text)
        }
        AppButton {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            theme: root.theme
            text: qsTr("+ %1°").arg(root.jointStepDeg.toFixed(1))
            enabled: root.controller.motionEnabled && !root.draftPending
            onClicked: root.controller.jogJoint(
                           root.jointIndex,
                           root.jointStepDeg,
                           root.motionSpeed)
        }
    }
}
