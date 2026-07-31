pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

GlassCard {
    id: root

    required property var controller
    property bool anyDraftPending: false

    implicitHeight: 190

    ColumnLayout {
        anchors.fill: parent
        spacing: 9

        SectionHeader {
            Layout.fillWidth: true
            theme: root.theme
            title: qsTr("ROS 2 链路")
            subtitle: root.anyDraftPending
                      ? qsTr("有未发送控制草稿；修复与停止已锁定") : ""
        }

        Item { Layout.fillHeight: true }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Repeater {
                model: [
                    { label: qsTr("自动启动 / 修复"), action: "ensure" },
                    { label: qsTr("查看状态"), action: "status" },
                    { label: qsTr("停止 ROS"), action: "stop" }
                ]

                AppButton {
                    required property var modelData

                    Layout.fillWidth: true
                    theme: root.theme
                    text: modelData.label
                    kind: modelData.action === "ensure" ? "primary" : "secondary"
                    enabled: root.controller.rosManagementEnabled
                             && (modelData.action === "status"
                                 || !root.anyDraftPending)
                    onClicked: root.controller.manageRos(modelData.action)
                }
            }
        }
    }
}
