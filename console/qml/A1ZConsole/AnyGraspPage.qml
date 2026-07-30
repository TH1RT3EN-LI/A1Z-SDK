pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Item {
    id: root

    required property var theme
    required property var controller

    ScrollView {
        anchors.fill: parent
        clip: true

        ColumnLayout {
            width: root.width
            spacing: root.theme.spacingM

            SectionHeader {
                Layout.fillWidth: true
                theme: root.theme
                title: qsTr("AnyGrasp 抓取链路")
            }

            GlassCard {
                Layout.fillWidth: true
                Layout.preferredHeight: 230
                theme: root.theme

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 10

                    SectionHeader {
                        Layout.fillWidth: true
                        theme: root.theme
                        title: qsTr("1. 只计算")
                    }

                    TextArea {
                        id: instruction
                        Layout.fillWidth: true
                        Layout.preferredHeight: 70
                        placeholderText: qsTr("例如：抓取桌面上的红色杯子")
                        text: qsTr("抓取桌面上的目标物体")
                        color: root.theme.text
                        placeholderTextColor: root.theme.tertiaryText
                        wrapMode: TextArea.Wrap
                        selectByMouse: true
                        background: Rectangle {
                            radius: root.theme.radiusControl
                            color: root.theme.tile
                            border.color: instruction.activeFocus
                                          ? root.theme.accent : root.theme.border
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        Text {
                            text: qsTr("规划器")
                            color: root.theme.secondaryText
                            font.family: root.theme.fontFamily
                            font.pixelSize: root.theme.typeLabel
                        }
                        ComboBox {
                            id: planner
                            Layout.preferredWidth: 150
                            model: ["adapter", "best"]
                        }

                        Text {
                            text: qsTr("视觉执行")
                            color: root.theme.secondaryText
                            font.family: root.theme.fontFamily
                            font.pixelSize: root.theme.typeLabel
                        }
                        ComboBox {
                            id: visionBackend
                            Layout.preferredWidth: 170
                            model: [
                                { text: qsTr("配置默认"), value: "auto" },
                                { text: qsTr("本机 GPU"), value: "local" },
                                { text: qsTr("远程 SSH GPU"), value: "remote_ssh" }
                            ]
                            textRole: "text"
                            valueRole: "value"
                        }

                        Item { Layout.fillWidth: true }

                        AppButton {
                            theme: root.theme
                            kind: "primary"
                            text: root.controller.taskBusy ? qsTr("计算中…") : qsTr("启动只计算")
                            enabled: !root.controller.taskBusy && !root.controller.commandBusy
                            onClicked: root.controller.computeAnyGrasp(
                                           instruction.text,
                                           planner.currentText,
                                           visionBackend.currentValue)
                        }

                        AppButton {
                            theme: root.theme
                            kind: "danger"
                            text: qsTr("中止任务")
                            visible: root.controller.taskBusy
                            onClicked: root.controller.cancelTask()
                        }
                    }
                }
            }

            GlassCard {
                Layout.fillWidth: true
                Layout.preferredHeight: 390
                theme: root.theme

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 9

                    SectionHeader {
                        Layout.fillWidth: true
                        theme: root.theme
                        title: qsTr("2. 审阅计算结果")
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 58
                        radius: root.theme.radiusControl
                        color: root.theme.tile
                        border.color: root.theme.border

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 10
                            spacing: 2

                            Text {
                                Layout.fillWidth: true
                                text: root.controller.graspSummary
                                color: root.theme.text
                                elide: Text.ElideRight
                                font.family: root.theme.fontFamily
                                font.pixelSize: root.theme.typeLabel
                                font.weight: Font.DemiBold
                            }
                            Text {
                                Layout.fillWidth: true
                                text: qsTr("Plan %1 · Frame %2")
                                      .arg(root.controller.planId || "—")
                                      .arg(root.controller.planFrame || "—")
                                color: root.theme.tertiaryText
                                elide: Text.ElideRight
                                font.family: root.theme.fontFamily
                                font.pixelSize: root.theme.typeCaption
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 7

                        Text {
                            text: qsTr("安全检查")
                            color: root.theme.secondaryText
                            font.family: root.theme.fontFamily
                            font.pixelSize: root.theme.typeCaption
                        }

                        Repeater {
                            model: root.controller.planSafety
                            StatusPill {
                                required property var modelData
                                theme: root.theme
                                text: modelData.name
                                level: modelData.ok ? "ok" : "error"
                            }
                        }

                        Item { Layout.fillWidth: true }

                        StatusPill {
                            theme: root.theme
                            text: root.controller.planSafetyPassed ? qsTr("全部通过")
                                                           : qsTr("未通过/无结果")
                            level: root.controller.planSafetyPassed ? "ok" : "error"
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 30
                        radius: root.theme.radiusSmall
                        color: root.theme.tile

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10

                            Text {
                                Layout.preferredWidth: 100
                                text: qsTr("轨迹段")
                                color: root.theme.tertiaryText
                                font.family: root.theme.fontFamily
                                font.pixelSize: root.theme.typeCaption
                            }
                            Text {
                                Layout.fillWidth: true
                                text: qsTr("目标关节角（度）")
                                color: root.theme.tertiaryText
                                font.family: root.theme.fontFamily
                                font.pixelSize: root.theme.typeCaption
                            }
                            Text {
                                Layout.preferredWidth: 70
                                text: qsTr("超时")
                                color: root.theme.tertiaryText
                                horizontalAlignment: Text.AlignRight
                                font.family: root.theme.fontFamily
                                font.pixelSize: root.theme.typeCaption
                            }
                        }
                    }

                    Repeater {
                        model: root.controller.planSegments

                        Rectangle {
                            id: segmentRow
                            required property var modelData
                            required property int index

                            Layout.fillWidth: true
                            Layout.preferredHeight: 38
                            radius: root.theme.radiusSmall
                            color: segmentRow.index % 2 ? root.theme.tile : "transparent"

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 10

                                Text {
                                    Layout.preferredWidth: 100
                                    text: segmentRow.modelData.index + ". " + segmentRow.modelData.type
                                    color: root.theme.text
                                    elide: Text.ElideRight
                                    font.family: root.theme.fontFamily
                                    font.pixelSize: root.theme.typeCaption
                                    font.weight: Font.DemiBold
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: "[" + segmentRow.modelData.jointsDeg.join(", ") + "]"
                                    color: root.theme.secondaryText
                                    elide: Text.ElideRight
                                    font.family: "monospace"
                                    font.pixelSize: root.theme.typeCaption
                                }
                                Text {
                                    Layout.preferredWidth: 70
                                    text: Number(segmentRow.modelData.timeoutS).toFixed(1) + " s"
                                    color: root.theme.tertiaryText
                                    horizontalAlignment: Text.AlignRight
                                    font.family: "monospace"
                                    font.pixelSize: root.theme.typeCaption
                                }
                            }
                        }
                    }

                    Item { Layout.fillHeight: true }
                }
            }

            GlassCard {
                Layout.fillWidth: true
                Layout.preferredHeight: 205
                theme: root.theme

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 10

                    SectionHeader {
                        Layout.fillWidth: true
                        theme: root.theme
                        title: qsTr("3. 执行已审阅计划")
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        TextField {
                            id: executePhrase
                            Layout.fillWidth: true
                            placeholderText: qsTr("实际执行请输入：执行 %1")
                                             .arg(root.controller.profile.toUpperCase())
                            color: root.theme.text
                            selectByMouse: true
                            background: Rectangle {
                                radius: root.theme.radiusControl
                                color: root.theme.tile
                                border.color: executePhrase.activeFocus
                                              ? root.theme.accent : root.theme.border
                            }
                        }

                        AppButton {
                            theme: root.theme
                            text: qsTr("仅演练计划")
                            enabled: root.controller.latestPlanPath.length > 0
                                     && !root.controller.taskBusy && !root.controller.commandBusy
                            onClicked: root.controller.executePlan(true, "")
                        }

                        AppButton {
                            theme: root.theme
                            kind: "danger"
                            text: qsTr("真实执行当前计划")
                            enabled: root.controller.latestPlanPath.length > 0
                                     && root.controller.planSafetyPassed
                                     && root.controller.motionEnabled
                            onClicked: root.controller.executePlan(false, executePhrase.text)
                        }
                    }
                }
            }
        }
    }
}
