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
                title: qsTr("A1Z 运行总览")
            }

            GlassCard {
                Layout.fillWidth: true
                Layout.preferredHeight: 366
                theme: root.theme

                ColumnLayout {
                    anchors.fill: parent
                    spacing: root.theme.spacingS

                    SectionHeader {
                        Layout.fillWidth: true
                        theme: root.theme
                        title: qsTr("六轴实时状态")
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 32
                        radius: root.theme.radiusSmall
                        color: root.theme.tile

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 12
                            anchors.rightMargin: 12
                            spacing: 8

                            Repeater {
                                model: [
                                    qsTr("关节"),
                                    qsTr("位置 °"),
                                    qsTr("速度 rad/s"),
                                    qsTr("力矩 Nm"),
                                    qsTr("MOS °C"),
                                    qsTr("错误")
                                ]
                                Text {
                                    required property string modelData
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 1
                                    text: modelData
                                    color: root.theme.tertiaryText
                                    horizontalAlignment: Text.AlignHCenter
                                    font.family: root.theme.fontFamily
                                    font.pixelSize: root.theme.typeCaption
                                    font.weight: Font.DemiBold
                                }
                            }
                        }
                    }

                    Repeater {
                        model: root.controller.joints

                        Rectangle {
                            id: jointRow
                            required property var modelData
                            required property int index

                            Layout.fillWidth: true
                            Layout.preferredHeight: 36
                            radius: root.theme.radiusSmall
                            color: jointRow.index % 2 === 0 ? "transparent" : root.theme.tile

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 12
                                spacing: 8

                                Text {
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 1
                                    text: jointRow.modelData.name
                                    color: root.theme.text
                                    horizontalAlignment: Text.AlignHCenter
                                    font.family: root.theme.fontFamily
                                    font.pixelSize: root.theme.typeLabel
                                    font.weight: Font.DemiBold
                                }
                                Text {
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 1
                                    text: Number(jointRow.modelData.position).toFixed(2)
                                    color: root.theme.text
                                    horizontalAlignment: Text.AlignHCenter
                                    font.family: "monospace"
                                    font.pixelSize: root.theme.typeLabel
                                }
                                Text {
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 1
                                    text: Number(jointRow.modelData.velocity).toFixed(3)
                                    color: root.theme.secondaryText
                                    horizontalAlignment: Text.AlignHCenter
                                    font.family: "monospace"
                                    font.pixelSize: root.theme.typeLabel
                                }
                                Text {
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 1
                                    text: Number(jointRow.modelData.torque).toFixed(3)
                                    color: root.theme.secondaryText
                                    horizontalAlignment: Text.AlignHCenter
                                    font.family: "monospace"
                                    font.pixelSize: root.theme.typeLabel
                                }
                                Text {
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 1
                                    text: Number(jointRow.modelData.tempMos) < 0 ? "—"
                                          : Number(jointRow.modelData.tempMos).toFixed(1)
                                    color: Number(jointRow.modelData.tempMos) >= 70
                                           ? root.theme.red : root.theme.secondaryText
                                    horizontalAlignment: Text.AlignHCenter
                                    font.family: "monospace"
                                    font.pixelSize: root.theme.typeLabel
                                }
                                Text {
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 1
                                    text: Number(jointRow.modelData.errorCode)
                                    color: Number(jointRow.modelData.errorCode) === 0
                                           ? root.theme.green : root.theme.red
                                    horizontalAlignment: Text.AlignHCenter
                                    font.family: "monospace"
                                    font.pixelSize: root.theme.typeLabel
                                }
                            }
                        }
                    }

                    Item { Layout.fillHeight: true }
                }
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
                        title: qsTr("链路状态")
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: root.theme.spacingS

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Layout.preferredWidth: 2
                            radius: root.theme.radiusControl
                            color: "#FF0B0E13"
                            border.color: root.controller.cameraReady
                                          ? root.theme.cyan : root.theme.border
                            border.width: 1
                            clip: true

                            Image {
                                anchors.fill: parent
                                anchors.margins: 6
                                source: root.controller.cameraPreviewSource
                                fillMode: Image.PreserveAspectFit
                                asynchronous: true
                                cache: false
                                smooth: true
                                visible: root.controller.cameraPreviewSource.length > 0
                            }

                            Text {
                                anchors.centerIn: parent
                                text: qsTr("等待 ROS RGB-D 预览")
                                visible: root.controller.cameraPreviewSource.length === 0
                                color: root.theme.tertiaryText
                                font.family: root.theme.fontFamily
                                font.pixelSize: root.theme.typeBody
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Layout.preferredWidth: 1
                            spacing: root.theme.spacingS

                            MetricTile {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                theme: root.theme
                                label: qsTr("RGB-D 相机")
                                value: root.controller.cameraSummary
                                accentColor: root.theme.cyan
                            }

                            MetricTile {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                theme: root.theme
                                label: qsTr("示教轨迹")
                                value: root.controller.recordingSummary
                                accentColor: root.theme.purple
                            }
                        }
                    }
                }
            }
        }
    }
}
