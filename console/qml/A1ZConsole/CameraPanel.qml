pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

GlassCard {
    id: root
    objectName: "cameraPanel"

    required property var controller

    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        SectionHeader {
            Layout.fillWidth: true
            theme: root.theme
            title: qsTr("RGB-D 相机")
        }

        GridLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            columns: root.width < 1000 ? 1 : 2
            columnSpacing: 12
            rowSpacing: 12

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumWidth: root.width < 1000 ? 0 : 520
                Layout.preferredHeight: root.width < 1000 ? 350 : -1
                radius: root.theme.radiusControl
                color: root.theme.mediaCanvas
                clip: true

                Image {
                    id: cameraPreview

                    objectName: "cameraPreview"
                    anchors.fill: parent
                    anchors.margins: 8
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
                    visible: status !== Image.Error
                             && root.controller.cameraPreviewAvailable
                }

                Column {
                    anchors.centerIn: parent
                    spacing: 8
                    visible: cameraPreview.status === Image.Error
                             || !root.controller.cameraPreviewAvailable

                    BusyIndicator {
                        anchors.horizontalCenter: parent.horizontalCenter
                        running: root.controller.cameraBusy
                        visible: running
                    }

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: cameraPreview.status === Image.Error
                              ? qsTr("画面解码失败，请刷新")
                              : root.controller.cameraBusy
                                ? qsTr("加载中…") : qsTr("暂无画面")
                        color: cameraPreview.status === Image.Error
                               ? root.theme.red : root.theme.tertiaryText
                        font.family: root.theme.fontFamily
                        font.pixelSize: root.theme.typeBody
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.preferredWidth: 390
                Layout.fillHeight: true
                spacing: 10

                StatusPill {
                    theme: root.theme
                    text: root.controller.cameraSummary
                    level: root.controller.cameraReady ? "ok" : "warn"
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    AppButton {
                        Layout.fillWidth: true
                        theme: root.theme
                        text: qsTr("检查链路")
                        enabled: !root.controller.cameraBusy
                        onClicked: root.controller.queryCamera("camera_status")
                    }

                    AppButton {
                        Layout.fillWidth: true
                        theme: root.theme
                        kind: "primary"
                        text: qsTr("刷新")
                        enabled: !root.controller.cameraBusy
                        onClicked: root.controller.queryCamera("camera_capture")
                    }
                }

                AppButton {
                    Layout.fillWidth: true
                    theme: root.theme
                    text: qsTr("读取外参")
                    enabled: !root.controller.cameraBusy
                    onClicked: root.controller.queryCamera("camera_extrinsic")
                }

                Text {
                    Layout.fillWidth: true
                    text: root.controller.cameraDetails
                    textFormat: Text.PlainText
                    color: root.theme.secondaryText
                    wrapMode: Text.Wrap
                    font.family: root.theme.fontFamily
                    font.pixelSize: root.theme.typeCaption
                }

                Item {
                    Layout.fillHeight: true
                }
            }
        }
    }
}
