pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

GlassCard {
    id: root

    required property var controller
    property bool armDraftPending: false
    property bool gripperDraftPending: false
    property bool anyDraftPending: false
    property string calibrationProfile: ""
    property bool calibrationConnected: false

    implicitHeight: 370

    onVisibleChanged: {
        if (!visible)
            calibrationPhrase.clear()
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 9

        SectionHeader {
            Layout.fillWidth: true
            theme: root.theme
            title: qsTr("CAN / 电机")
            subtitle: root.armDraftPending || root.gripperDraftPending
                      ? qsTr("影响同一设备的维护操作已锁定") : ""
        }

        GridLayout {
            Layout.fillWidth: true
            columns: 3
            columnSpacing: 8
            rowSpacing: 8

            AppButton {
                Layout.fillWidth: true
                theme: root.theme
                text: qsTr("检查 CAN")
                enabled: root.controller.hardwareInspectionEnabled
                onClicked: root.controller.runMaintenance("can_check", "")
            }
            AppButton {
                Layout.fillWidth: true
                theme: root.theme
                text: qsTr("监听 5 秒")
                enabled: root.controller.offlineMaintenanceEnabled
                onClicked: root.controller.runMaintenance("motor_listen", "")
            }
            AppButton {
                Layout.fillWidth: true
                theme: root.theme
                text: qsTr("扫描电机")
                enabled: root.controller.offlineMaintenanceEnabled
                         && !root.armDraftPending
                         && !root.gripperDraftPending
                onClicked: root.controller.runMaintenance("motor_scan", "")
            }
            AppButton {
                Layout.fillWidth: true
                theme: root.theme
                text: qsTr("G1Z 混控测试")
                enabled: root.controller.offlineMaintenanceEnabled
                         && !root.gripperDraftPending
                onClicked: root.controller.runMaintenance("gripper_test", "")
            }
        }

        Item { Layout.fillHeight: true }

        RowLayout {
            Layout.fillWidth: true
            visible: root.controller.offlineMaintenanceSupported
                     && root.controller.connected

            Text {
                Layout.fillWidth: true
                text: qsTr("直连 CAN 已锁定：控制服务仍在线")
                color: root.theme.orange
                font.family: root.theme.fontFamily
                font.pixelSize: root.theme.typeCaption
            }
            AppButton {
                objectName: "unlockOfflineMaintenanceButton"
                theme: root.theme
                text: qsTr("停止控制服务后解锁")
                enabled: root.controller.serviceStopEnabled
                         && !root.anyDraftPending
                onClicked: root.controller.stopServer()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: root.theme.border
        }

        Text {
            Layout.fillWidth: true
            text: qsTr("校零将当前姿态写为零点")
            color: root.theme.red
            font.family: root.theme.fontFamily
            font.pixelSize: root.theme.typeCaption
            font.weight: Font.DemiBold
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            AppTextField {
                id: calibrationPhrase
                Layout.fillWidth: true
                theme: root.theme
                dangerFocus: true
                placeholderText: qsTr("输入：校零 A1Z")
                Accessible.name: qsTr("校零确认短语")
            }
            AppButton {
                theme: root.theme
                kind: "danger"
                text: qsTr("六轴校零")
                enabled: root.controller.offlineMaintenanceEnabled
                         && !root.armDraftPending
                         && calibrationPhrase.text.trim() === "校零 A1Z"
                onClicked: {
                    root.controller.runMaintenance(
                                "set_zero_all", calibrationPhrase.text)
                    calibrationPhrase.clear()
                }
            }
            AppButton {
                theme: root.theme
                kind: "danger"
                text: qsTr("夹爪校零")
                enabled: root.controller.offlineMaintenanceEnabled
                         && !root.gripperDraftPending
                         && calibrationPhrase.text.trim() === "校零 A1Z"
                onClicked: {
                    root.controller.runMaintenance(
                                "set_zero_gripper", calibrationPhrase.text)
                    calibrationPhrase.clear()
                }
            }
        }
    }

    Connections {
        target: root.controller

        function onStateChanged() {
            if (root.calibrationProfile !== root.controller.profile
                    || root.calibrationConnected !== root.controller.connected) {
                root.calibrationProfile = root.controller.profile
                root.calibrationConnected = root.controller.connected
                calibrationPhrase.clear()
            }
        }
    }

    Component.onCompleted: {
        root.calibrationProfile = root.controller.profile
        root.calibrationConnected = root.controller.connected
    }
}
