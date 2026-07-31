pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

GlassCard {
    id: root

    required property var controller

    implicitHeight: 112

    RowLayout {
        anchors.fill: parent
        spacing: 10

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 3

            Text {
                text: qsTr("末端位姿")
                color: root.theme.tertiaryText
                font.family: root.theme.fontFamily
                font.pixelSize: root.theme.typeCaption
            }
            Text {
                Layout.fillWidth: true
                text: root.controller.eePoseText
                textFormat: Text.PlainText
                color: root.theme.text
                elide: Text.ElideRight
                font.family: "monospace"
                font.pixelSize: root.theme.typeLabel
                font.weight: Font.DemiBold
            }
            Text {
                Layout.fillWidth: true
                text: root.controller.eeAxisText
                textFormat: Text.PlainText
                color: root.theme.secondaryText
                elide: Text.ElideRight
                font.family: "monospace"
                font.pixelSize: root.theme.typeCaption
            }
            Text {
                Layout.fillWidth: true
                text: root.controller.eeMotionText
                textFormat: Text.PlainText
                color: root.theme.tertiaryText
                elide: Text.ElideRight
                font.family: root.theme.fontFamily
                font.pixelSize: root.theme.typeCaption
            }
        }

        AppButton {
            theme: root.theme
            text: qsTr("读取 FK")
            enabled: root.controller.kinematicsReadEnabled
            onClicked: root.controller.refreshKinematics()
        }
    }
}
