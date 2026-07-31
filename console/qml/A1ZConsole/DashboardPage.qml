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
                Layout.preferredHeight: 366
                theme: root.theme

                ColumnLayout {
                    anchors.fill: parent
                    spacing: root.theme.spacingS

                    SectionHeader {
                        Layout.fillWidth: true
                        theme: root.theme
                        title: qsTr("关节状态")
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
                                    qsTr("电机状态")
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
                            radius: 0
                            color: "transparent"

                            Rectangle {
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                height: 1
                                visible: jointRow.index < 5
                                color: root.theme.separator
                            }

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
                                    text: jointRow.modelData.errorStatus
                                    color: jointRow.modelData.errorIsFault
                                           ? root.theme.red
                                           : jointRow.index >= 3
                                             && Number(jointRow.modelData.errorCode) === 1
                                             ? root.theme.green
                                             : root.theme.secondaryText
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
                Layout.preferredHeight: Math.max(
                                            230,
                                            root.height - 366
                                            - root.theme.spacingM)
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
                            color: root.theme.mediaCanvas
                            border.width: 0
                            clip: true

                            Image {
                                objectName: "dashboardCameraPreview"
                                readonly property int loadStatus: status
                                anchors.fill: parent
                                anchors.margins: 6
                                source: root.visible
                                        ? root.controller.cameraPreviewSource : ""
                                sourceSize.width: Math.min(
                                                      960,
                                                      Math.max(1, Math.ceil(width)))
                                fillMode: Image.PreserveAspectFit
                                asynchronous: true
                                cache: false
                                retainWhileLoading: true
                                smooth: true
                                visible: root.controller.cameraPreviewSource.length > 0
                            }

                            Text {
                                anchors.centerIn: parent
                                text: qsTr("暂无画面")
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
                            }

                            MetricTile {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                theme: root.theme
                                label: qsTr("示教轨迹")
                                value: root.controller.recordingSummary
                            }
                        }
                    }
                }
            }
        }
    }
}
