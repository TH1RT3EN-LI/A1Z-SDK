pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

GlassCard {
    id: root

    required property var controller
    signal routeRequested(string route)

    readonly property var steps: [
        {
            title: qsTr("1 · 控制服务 / CAN"),
            ready: root.controller.startupControlReady,
            status: root.controller.startupControlReady
                    ? qsTr("SocketCAN 与位置保持已就绪")
                    : root.controller.faulted
                      ? root.controller.faultMessage
                      : root.controller.connected
                        ? qsTr("服务在线，但控制尚未就绪")
                        : qsTr("启动时会自动配置 can0 @ 1 Mbps"),
            action: root.controller.connected ? "settings" : "control",
            button: root.controller.connected
                    ? qsTr("查看运行配置") : qsTr("启动控制服务"),
            enabled: root.controller.connected
                     || root.controller.serviceStartEnabled,
            busy: root.controller.taskKind === "server_start"
        },
        {
            title: qsTr("2 · ROS 2 链路"),
            ready: root.controller.startupRosReady,
            status: root.controller.startupRosReady
                    ? qsTr("相机桥已连接")
                    : qsTr("启动相机、机器人状态与运动节点"),
            action: "ros",
            button: qsTr("自动启动 / 修复 ROS"),
            enabled: root.controller.rosManagementEnabled,
            busy: root.controller.taskKind === "ros"
        },
        {
            title: qsTr("3 · RGB-D 帧"),
            ready: root.controller.startupCameraReady,
            status: root.controller.startupCameraReady
                    ? root.controller.cameraSummary
                    : qsTr("等待新鲜且同步的颜色/深度帧"),
            action: root.controller.startupRosReady ? "camera" : "ros",
            button: root.controller.startupRosReady
                    ? qsTr("检查 RGB-D 帧") : qsTr("先启动 ROS"),
            enabled: root.controller.startupRosReady
                     ? !root.controller.cameraBusy
                     : root.controller.rosManagementEnabled,
            busy: root.controller.cameraBusy
                  || root.controller.taskKind === "ros"
        },
        {
            title: qsTr("4 · 全链路预检"),
            ready: root.controller.startupPreflightReady,
            status: root.controller.preflightStatus,
            action: "preflight",
            button: root.controller.preflightState === "running"
                    ? qsTr("预检中…") : qsTr("运行最终预检"),
            enabled: root.controller.startupControlReady
                     && root.controller.startupCameraReady
                     && root.controller.diagnosticsEnabled,
            busy: root.controller.taskKind === "preflight"
        }
    ]

    function runAction(action) {
        if (action === "control")
            root.controller.startServer(false, 1.0)
        else if (action === "ros")
            root.controller.ensureRos()
        else if (action === "camera")
            root.controller.queryCamera("camera_capture")
        else if (action === "preflight")
            root.controller.runPreflight()
        else if (action === "settings")
            root.routeRequested("settings")
    }

    implicitHeight: guideColumn.implicitHeight + 2 * padding

    ColumnLayout {
        id: guideColumn
        anchors.fill: parent
        spacing: root.theme.spacingS

        RowLayout {
            Layout.fillWidth: true

            SectionHeader {
                Layout.fillWidth: true
                theme: root.theme
                title: qsTr("启动引导")
                subtitle: root.controller.startupReady
                          ? qsTr("所有必需链路已验证，控制入口已解锁")
                          : qsTr("按顺序完成后才开放控制页")
            }

            StatusPill {
                theme: root.theme
                text: root.controller.startupReady
                      ? qsTr("已解锁") : qsTr("启动未完成")
                level: root.controller.startupReady ? "ok" : "warn"
            }
        }

        GridLayout {
            Layout.fillWidth: true
            columns: 4
            columnSpacing: root.theme.spacingS
            rowSpacing: root.theme.spacingS

            Repeater {
                model: root.steps

                Rectangle {
                    id: stepTile
                    required property var modelData

                    Layout.fillWidth: true
                    Layout.preferredHeight: 142
                    radius: root.theme.radiusControl
                    color: root.theme.tile
                    border.width: 1
                    border.color: stepTile.modelData.ready
                                  ? root.theme.green : root.theme.separator

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 7

                        RowLayout {
                            Layout.fillWidth: true

                            Text {
                                Layout.fillWidth: true
                                text: stepTile.modelData.title
                                color: root.theme.text
                                font.family: root.theme.fontFamily
                                font.pixelSize: root.theme.typeLabel
                                font.weight: Font.DemiBold
                            }

                            StatusPill {
                                theme: root.theme
                                text: stepTile.modelData.ready
                                      ? qsTr("通过") : qsTr("待完成")
                                level: stepTile.modelData.ready ? "ok" : "warn"
                            }
                        }

                        Text {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            text: stepTile.modelData.status
                            textFormat: Text.PlainText
                            color: stepTile.modelData.ready
                                   ? root.theme.secondaryText
                                   : root.theme.tertiaryText
                            wrapMode: Text.Wrap
                            maximumLineCount: 2
                            elide: Text.ElideRight
                            font.family: root.theme.fontFamily
                            font.pixelSize: root.theme.typeCaption
                        }

                        AppButton {
                            Layout.fillWidth: true
                            theme: root.theme
                            kind: stepTile.modelData.ready
                                  ? "quiet" : "secondary"
                            text: stepTile.modelData.ready
                                  ? qsTr("已完成")
                                  : stepTile.modelData.button
                            enabled: !stepTile.modelData.ready
                                     && stepTile.modelData.enabled
                            busy: stepTile.modelData.busy
                            onClicked: root.runAction(stepTile.modelData.action)
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true

            Text {
                Layout.fillWidth: true
                text: root.controller.startupGateText
                color: root.controller.startupReady
                       ? root.theme.green : root.theme.orange
                elide: Text.ElideRight
                font.family: root.theme.fontFamily
                font.pixelSize: root.theme.typeCaption
            }

            AppButton {
                theme: root.theme
                kind: "primary"
                text: qsTr("进入手动控制")
                enabled: root.controller.startupReady
                onClicked: root.routeRequested("manual")
            }
        }
    }
}
