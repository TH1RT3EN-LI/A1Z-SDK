pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

GlassCard {
    id: root
    objectName: "graspComputePanel"

    required property var controller

    implicitHeight: Math.max(
                        190,
                        computeColumn.implicitHeight + 2 * root.padding)

    ColumnLayout {
        id: computeColumn

        anchors.fill: parent
        spacing: 10

        SectionHeader {
            Layout.fillWidth: true
            theme: root.theme
            title: qsTr("1. 计算")
            subtitle: root.controller.planState === "computing"
                      ? root.controller.planStatus : ""
        }

        AppTextArea {
            id: instruction

            Layout.fillWidth: true
            Layout.preferredHeight: 70
            theme: root.theme
            placeholderText: qsTr("输入抓取目标")
            text: qsTr("抓取目标物体")
            Accessible.name: qsTr("抓取目标")
            wrapMode: TextArea.Wrap
            enabled: root.controller.planningEnabled
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Text {
                text: qsTr("规划")
                color: root.theme.secondaryText
                font.family: root.theme.fontFamily
                font.pixelSize: root.theme.typeLabel
            }

            AppComboBox {
                id: planner

                Layout.preferredWidth: 150
                theme: root.theme
                model: [
                    { text: qsTr("适配器规划"), value: "adapter" },
                    { text: qsTr("最优候选"), value: "best" }
                ]
                textRole: "text"
                valueRole: "value"
                Accessible.name: qsTr("抓取规划方式")
                enabled: root.controller.planningEnabled
            }

            Text {
                text: qsTr("视觉")
                color: root.theme.secondaryText
                font.family: root.theme.fontFamily
                font.pixelSize: root.theme.typeLabel
            }

            AppComboBox {
                id: visionBackend

                Layout.preferredWidth: 170
                theme: root.theme
                model: [
                    {
                        text: root.controller.profileName === "real"
                              ? qsTr("默认：远程 SSH GPU")
                              : qsTr("默认：本机 GPU"),
                        value: "auto"
                    },
                    { text: qsTr("本机 GPU"), value: "local" },
                    { text: qsTr("远程 SSH GPU"), value: "remote_ssh" }
                ]
                textRole: "text"
                valueRole: "value"
                Accessible.name: qsTr("视觉计算位置")
                enabled: root.controller.planningEnabled
            }

            Item {
                Layout.fillWidth: true
            }

            AppButton {
                theme: root.theme
                kind: "primary"
                text: root.controller.taskKind === "anygrasp_compute"
                      ? qsTr("计算中…")
                      : root.controller.taskBusy
                        ? qsTr("其他任务占用")
                        : qsTr("开始计算")
                enabled: root.controller.planningEnabled
                onClicked: root.controller.computeAnyGrasp(
                               instruction.text,
                               planner.currentValue,
                               visionBackend.currentValue)
            }
        }
    }
}
