pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

GlassCard {
    id: root

    required property var controller

    implicitHeight: Math.max(250, checkColumn.implicitHeight + 2 * padding)

    ColumnLayout {
        id: checkColumn
        anchors.fill: parent
        spacing: 8

        RowLayout {
            Layout.fillWidth: true

            SectionHeader {
                Layout.fillWidth: true
                theme: root.theme
                title: qsTr("全链路预检")
                subtitle: root.controller.preflightStatus
            }

            StatusPill {
                theme: root.theme
                visible: root.controller.preflightState !== "idle"
                text: root.controller.preflightState === "running"
                      ? qsTr("检查中")
                      : root.controller.preflightState === "ready"
                        ? qsTr("已就绪")
                        : root.controller.preflightState === "issues"
                          ? qsTr("有问题") : qsTr("结果无效")
                level: root.controller.preflightState === "ready"
                       ? "ok"
                       : root.controller.preflightState === "running"
                         || root.controller.preflightState === "issues"
                         ? "warn" : "error"
            }

            AppButton {
                theme: root.theme
                kind: "primary"
                text: root.controller.taskKind === "preflight"
                      ? qsTr("检查中…")
                      : root.controller.taskBusy
                        ? qsTr("其他任务占用")
                        : qsTr("运行预检")
                enabled: root.controller.diagnosticsEnabled
                onClicked: root.controller.runPreflight()
            }
        }

        Repeater {
            model: root.controller.preflightItems

            Item {
                id: preflightRow

                required property var modelData
                required property int index

                Layout.fillWidth: true
                Layout.preferredHeight: detailText.implicitHeight + 22

                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: 1
                    visible: preflightRow.index
                             < root.controller.preflightItems.length - 1
                    color: root.theme.separator
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 10
                    spacing: 10

                    StatusPill {
                        theme: root.theme
                        text: preflightRow.modelData.ok
                              ? qsTr("通过") : qsTr("失败")
                        level: preflightRow.modelData.ok
                               ? "ok"
                               : preflightRow.modelData.severity === "advisory"
                                 ? "warn" : "error"
                    }
                    Text {
                        Layout.preferredWidth: 120
                        text: preflightRow.modelData.name
                        textFormat: Text.PlainText
                        color: root.theme.text
                        font.family: root.theme.fontFamily
                        font.pixelSize: root.theme.typeLabel
                        font.weight: Font.DemiBold
                    }
                    Text {
                        id: detailText
                        Layout.fillWidth: true
                        text: preflightRow.modelData.detail
                        textFormat: Text.PlainText
                        color: root.theme.secondaryText
                        wrapMode: Text.WrapAnywhere
                        font.family: root.theme.fontFamily
                        font.pixelSize: root.theme.typeCaption
                    }
                }
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 110
            visible: root.controller.preflightItems.length === 0

            Text {
                anchors.centerIn: parent
                text: root.controller.preflightState === "running"
                      ? qsTr("正在收集检查结果…")
                      : root.controller.preflightState === "failed"
                        || root.controller.preflightState === "invalid"
                        ? root.controller.preflightStatus
                        : qsTr("运行预检后显示控制、遥测、相机与环境状态")
                color: root.controller.preflightState === "failed"
                       || root.controller.preflightState === "invalid"
                       ? root.theme.red : root.theme.tertiaryText
                font.family: root.theme.fontFamily
                font.pixelSize: root.theme.typeLabel
            }
        }
    }
}
