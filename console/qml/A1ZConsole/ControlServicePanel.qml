pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

GlassCard {
    id: root
    objectName: "controlServicePanel"

    required property var controller
    property real gravityFactor: 1.0
    property bool controlTargetPending: false
    property bool configurationDraftPending: false
    readonly property bool operationBlocked:
        root.controlTargetPending
        || (root.controller.connected && root.configurationDraftPending)

    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        SectionHeader {
            Layout.fillWidth: true
            theme: root.theme
            title: qsTr("控制服务")
        }

        StatusPill {
            theme: root.theme
            text: root.controller.connected
                  ? qsTr("%1 已连接").arg(root.controller.backendLabel)
                  : qsTr("服务离线")
            level: root.controller.connected ? "ok" : "warn"
        }

        AppButton {
            Layout.fillWidth: true
            theme: root.theme
            kind: root.controller.connected ? "secondary" : "primary"
            text: root.controller.connected
                  ? qsTr("停止 %1 控制服务").arg(
                        root.controller.profile.toUpperCase())
                  : root.controller.serviceStartEnabled
                    ? qsTr("启动 %1 控制服务").arg(
                          root.controller.profile.toUpperCase())
                    : qsTr("控制状态未确认 · 禁止启动")
            enabled: root.controller.connected
                     ? root.controller.serviceStopEnabled
                       && !root.operationBlocked
                     : root.controller.serviceStartEnabled
                       && !root.operationBlocked
            onClicked: {
                if (root.controller.connected)
                    root.controller.stopServer()
                else
                    root.controller.startServer(false, root.gravityFactor)
            }
        }

        Text {
            Layout.fillWidth: true
            text: root.operationBlocked
                  ? root.controlTargetPending
                    ? qsTr("有未发送控制目标；请先发送或放弃")
                    : qsTr("有未应用的重力补偿系数；停止服务前请先应用或放弃")
                  : root.controller.connected
                  ? qsTr("已确认 %1 · %2")
                    .arg(root.controller.backendLabel)
                    .arg(root.controller.endpoint)
                  : qsTr("端点 %1 · 启动仅在已确认离线时开放")
                    .arg(root.controller.endpoint)
            color: root.theme.tertiaryText
            elide: Text.ElideRight
            font.family: "monospace"
            font.pixelSize: root.theme.typeCaption
        }
    }
}
