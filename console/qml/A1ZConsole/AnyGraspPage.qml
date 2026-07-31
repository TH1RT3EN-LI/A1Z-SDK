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

            GlassCard {
                Layout.fillWidth: true
                Layout.preferredHeight: 190
                theme: root.theme

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 10

                    SectionHeader {
                        Layout.fillWidth: true
                        theme: root.theme
                        title: qsTr("1. 计算")
                    }

                    AppTextArea {
                        id: instruction
                        Layout.fillWidth: true
                        Layout.preferredHeight: 70
                        theme: root.theme
                        placeholderText: qsTr("输入抓取目标")
                        text: qsTr("抓取目标物体")
                        wrapMode: TextArea.Wrap
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
                            text: root.controller.taskBusy ? qsTr("计算中…") : qsTr("开始计算")
                            enabled: !root.controller.taskBusy && !root.controller.commandBusy
                            onClicked: root.controller.computeAnyGrasp(
                                           instruction.text,
                                           planner.currentValue,
                                           visionBackend.currentValue)
                        }

                        AppButton {
                            theme: root.theme
                            kind: "danger"
                            text: qsTr("中止")
                            visible: root.controller.taskBusy
                            onClicked: root.controller.cancelTask()
                        }
                    }
                }
            }

            GlassCard {
                Layout.fillWidth: true
                Layout.preferredHeight: Math.max(
                                            root.controller.planSegments.length === 0
                                            ? 158
                                            : Math.max(
                                                  260,
                                                  170
                                                  + root.controller.planSegments.length
                                                  * 38),
                                            root.height - 190 - 120
                                            - 2 * root.theme.spacingM)
                theme: root.theme

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 9

                    SectionHeader {
                        Layout.fillWidth: true
                        theme: root.theme
                        title: qsTr("2. 审阅")
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 58
                        radius: root.theme.radiusControl
                        color: root.theme.tile
                        border.width: 0

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
                        visible: root.controller.planSegments.length > 0
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
                        visible: root.controller.planSegments.length > 0
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
                            radius: 0
                            color: "transparent"

                            Rectangle {
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                height: 1
                                visible: segmentRow.index
                                         < root.controller.planSegments.length - 1
                                color: root.theme.separator
                            }

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

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.minimumHeight: 58
                        visible: root.controller.planSegments.length === 0
                        radius: root.theme.radiusControl
                        color: "transparent"
                        border.width: 0

                        Column {
                            anchors.centerIn: parent
                            spacing: 4

                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: qsTr("暂无计划")
                                color: root.theme.secondaryText
                                font.family: root.theme.fontFamily
                                font.pixelSize: root.theme.typeLabel
                                font.weight: Font.DemiBold
                            }
                        }
                    }

                    Item { Layout.fillHeight: true }
                }
            }

            GlassCard {
                Layout.fillWidth: true
                Layout.preferredHeight: 120
                theme: root.theme

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 10

                    SectionHeader {
                        Layout.fillWidth: true
                        theme: root.theme
                        title: qsTr("3. 执行")
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        AppTextField {
                            id: executePhrase
                            Layout.fillWidth: true
                            theme: root.theme
                            placeholderText: qsTr("输入：执行 %1")
                                             .arg(root.controller.profile.toUpperCase())
                        }

                        AppButton {
                            theme: root.theme
                            text: qsTr("演练")
                            enabled: root.controller.latestPlanPath.length > 0
                                     && !root.controller.taskBusy && !root.controller.commandBusy
                            onClicked: root.controller.executePlan(true, "")
                        }

                        AppButton {
                            theme: root.theme
                            kind: "danger"
                            text: qsTr("执行计划")
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
