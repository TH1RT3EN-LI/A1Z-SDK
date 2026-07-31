pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

GlassCard {
    id: root
    objectName: "presetMotionPanel"

    required property var controller
    property real motionSpeed: 0.5
    property bool armDraftPending: false

    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        SectionHeader {
            Layout.fillWidth: true
            theme: root.theme
            title: qsTr("预置动作")
            subtitle: root.armDraftPending
                      ? qsTr("有未发送关节目标；请先发送或重新载入")
                      : ""
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Text {
                Layout.preferredWidth: 84
                text: qsTr("单一姿态")
                color: root.theme.secondaryText
                font.family: root.theme.fontFamily
                font.pixelSize: root.theme.typeLabel
            }

            AppComboBox {
                id: presetSelection

                Layout.fillWidth: true
                theme: root.theme
                model: [
                    { text: qsTr("归位姿态"), value: "home" },
                    { text: qsTr("准备姿态"), value: "ready" },
                    { text: qsTr("前伸姿态"), value: "reach" },
                    { text: qsTr("致意姿态"), value: "salute" },
                    { text: qsTr("左挥姿态"), value: "wave_l" },
                    { text: qsTr("右挥姿态"), value: "wave_r" },
                    { text: qsTr("点头起始姿态"), value: "nod_a" },
                    { text: qsTr("点头结束姿态"), value: "nod_b" },
                    { text: qsTr("摇头左姿态"), value: "shake_a" },
                    { text: qsTr("摇头右姿态"), value: "shake_b" },
                    { text: qsTr("鞠躬姿态"), value: "bow" }
                ]
                textRole: "text"
                valueRole: "value"
                Accessible.name: qsTr("预置姿态")
                enabled: root.controller.motionEnabled
                         && !root.armDraftPending
            }

            AppButton {
                Layout.preferredWidth: 154
                theme: root.theme
                kind: "primary"
                text: qsTr("移动到所选姿态")
                enabled: root.controller.motionEnabled
                         && !root.armDraftPending
                onClicked: root.controller.movePreset(
                               presetSelection.currentValue,
                               root.motionSpeed)
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Text {
                Layout.preferredWidth: 84
                text: qsTr("动作序列")
                color: root.theme.secondaryText
                font.family: root.theme.fontFamily
                font.pixelSize: root.theme.typeLabel
            }

            AppComboBox {
                id: danceSelection

                Layout.fillWidth: true
                theme: root.theme
                model: [
                    { text: qsTr("致意序列（归位后返回）"), value: "salute" },
                    { text: qsTr("挥手序列（归位后返回）"), value: "wave" },
                    { text: qsTr("点头序列（归位后返回）"), value: "nod" },
                    { text: qsTr("摇头序列（归位后返回）"), value: "shake" },
                    { text: qsTr("前伸序列（归位后返回）"), value: "reach" },
                    { text: qsTr("鞠躬序列（归位后返回）"), value: "bow" },
                    { text: qsTr("完整序列（全部动作后返回）"), value: "all" }
                ]
                textRole: "text"
                valueRole: "value"
                Accessible.name: qsTr("动作序列")
                enabled: root.controller.motionEnabled
                         && !root.armDraftPending
            }

            AppButton {
                Layout.preferredWidth: 154
                theme: root.theme
                kind: danceSelection.currentValue === "all"
                      ? "danger" : "primary"
                text: danceSelection.currentValue === "all"
                      ? qsTr("运行完整序列")
                      : qsTr("运行所选序列")
                enabled: root.controller.motionEnabled
                         && !root.armDraftPending
                onClicked: root.controller.runDance(
                               danceSelection.currentValue,
                               root.motionSpeed)
            }
        }
    }
}
