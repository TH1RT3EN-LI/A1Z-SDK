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
    readonly property int selectedMotorNumber: motorSelector.currentIndex + 1
    readonly property bool selectedMotorSupportsClear:
        root.selectedMotorNumber >= 4
    readonly property string selectedMotorName:
        "J" + root.selectedMotorNumber

    implicitHeight: 560

    onVisibleChanged: {
        if (!visible) {
            motorClearPhrase.clear()
            calibrationPhrase.clear()
        }
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

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: root.theme.border
        }

        Text {
            Layout.fillWidth: true
            text: qsTr("单电机检查会短暂使能后失能选中轴；操作前请支撑机械臂")
            color: root.theme.orange
            wrapMode: Text.Wrap
            textFormat: Text.PlainText
            font.family: root.theme.fontFamily
            font.pixelSize: root.theme.typeCaption
            font.weight: Font.DemiBold
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            AppComboBox {
                id: motorSelector
                Layout.preferredWidth: 190
                theme: root.theme
                currentIndex: 3
                model: [
                    qsTr("J1 · MotorA"),
                    qsTr("J2 · MotorA"),
                    qsTr("J3 · MotorA"),
                    qsTr("J4 · MotorB 4340"),
                    qsTr("J5 · MotorB 4310"),
                    qsTr("J6 · MotorB 4310")
                ]
                Accessible.name: qsTr("单电机选择")
                onActivated: motorClearPhrase.clear()
            }
            AppButton {
                Layout.preferredWidth: 128
                theme: root.theme
                text: qsTr("检查 ") + root.selectedMotorName
                enabled: root.controller.offlineMaintenanceEnabled
                         && !root.armDraftPending
                onClicked: root.controller.runMaintenance(
                               "motor_check_j" + root.selectedMotorNumber, "")
            }
            Text {
                Layout.fillWidth: true
                text: root.selectedMotorSupportsClear
                      ? qsTr("检查结果会显示位置、温度和错误码")
                      : qsTr("J1–J3 为 MotorA，官方 SDK 不支持 0xFB 清错")
                color: root.selectedMotorSupportsClear
                       ? root.theme.secondaryText : root.theme.tertiaryText
                wrapMode: Text.Wrap
                textFormat: Text.PlainText
                font.family: root.theme.fontFamily
                font.pixelSize: root.theme.typeCaption
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            AppTextField {
                id: motorClearPhrase
                Layout.fillWidth: true
                theme: root.theme
                dangerFocus: true
                enabled: root.selectedMotorSupportsClear
                placeholderText: root.selectedMotorSupportsClear
                                 ? qsTr("输入：清错 ") + root.selectedMotorName
                                 : qsTr("仅 J4–J6 支持官方清错指令")
                Accessible.name: qsTr("单电机清错确认短语")
            }
            AppButton {
                Layout.preferredWidth: 128
                theme: root.theme
                kind: "danger"
                text: qsTr("清除 ") + root.selectedMotorName + qsTr(" 错误")
                enabled: root.controller.offlineMaintenanceEnabled
                         && !root.armDraftPending
                         && root.selectedMotorSupportsClear
                         && motorClearPhrase.text.trim()
                            === "清错 " + root.selectedMotorName
                onClicked: {
                    root.controller.runMaintenance(
                                "motor_clear_j" + root.selectedMotorNumber,
                                motorClearPhrase.text)
                    motorClearPhrase.clear()
                }
            }
        }

        Text {
            Layout.fillWidth: true
            text: qsTr("清错只解除故障锁存，不会修复欠压、过温或接线问题；清除后请再点“检查”确认")
            color: root.theme.red
            wrapMode: Text.Wrap
            textFormat: Text.PlainText
            font.family: root.theme.fontFamily
            font.pixelSize: root.theme.typeCaption
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
