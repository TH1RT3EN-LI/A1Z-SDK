pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Item {
    id: root

    required property var theme
    required property var controller

    RowLayout {
        anchors.fill: parent
        spacing: root.theme.spacingM

        ScrollView {
            id: diagnosticsScroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredWidth: 0.54 * root.width
            clip: true

            ColumnLayout {
                width: diagnosticsScroll.availableWidth
                spacing: root.theme.spacingM

                GlassCard {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.max(250, checkColumn.implicitHeight + 34)
                    theme: root.theme

                    ColumnLayout {
                        id: checkColumn
                        anchors.fill: parent
                        spacing: 8

                        RowLayout {
                            Layout.fillWidth: true

                            SectionHeader {
                                Layout.fillWidth: true
                                theme: root.theme
                                title: qsTr("全链路预检")
                            }

                            AppButton {
                                theme: root.theme
                                kind: "primary"
                                text: root.controller.taskBusy ? qsTr("检查中…") : qsTr("运行预检")
                                enabled: !root.controller.taskBusy && !root.controller.commandBusy
                                onClicked: root.controller.runPreflight()
                            }
                        }

                        Repeater {
                            model: root.controller.preflightItems

                            Rectangle {
                                id: preflightRow
                                required property var modelData
                                required property int index

                                Layout.fillWidth: true
                                Layout.preferredHeight: detailText.implicitHeight + 22
                                radius: 0
                                color: "transparent"

                                Rectangle {
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.bottom: parent.bottom
                                    height: 1
                                    visible: preflightRow.index
                                             < root.controller.preflightItems.length - 1
                                    color: root.theme.separator
                                }

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 10
                                    anchors.rightMargin: 10
                                    spacing: 10

                                    StatusPill {
                                        theme: root.theme
                                        text: preflightRow.modelData.ok ? qsTr("通过") : qsTr("失败")
                                        level: preflightRow.modelData.ok ? "ok"
                                               : preflightRow.modelData.severity === "advisory"
                                                 ? "warn" : "error"
                                    }
                                    Text {
                                        Layout.preferredWidth: 120
                                        text: preflightRow.modelData.name
                                        color: root.theme.text
                                        font.family: root.theme.fontFamily
                                        font.pixelSize: root.theme.typeLabel
                                        font.weight: Font.DemiBold
                                    }
                                    Text {
                                        id: detailText
                                        Layout.fillWidth: true
                                        text: preflightRow.modelData.detail
                                        color: root.theme.secondaryText
                                        wrapMode: Text.WrapAnywhere
                                        font.family: root.theme.fontFamily
                                        font.pixelSize: root.theme.typeCaption
                                    }
                                }
                            }
                        }

                        Item {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            visible: root.controller.preflightItems.length === 0

                            Text {
                                anchors.centerIn: parent
                                text: qsTr("暂无结果")
                                color: root.theme.tertiaryText
                                font.family: root.theme.fontFamily
                                font.pixelSize: root.theme.typeLabel
                            }
                        }

                        Item {
                            Layout.fillHeight: true
                            visible: root.controller.preflightItems.length > 0
                        }
                    }
                }

                GlassCard {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 190
                    theme: root.theme

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 9

                        SectionHeader {
                            Layout.fillWidth: true
                            theme: root.theme
                            title: qsTr("ROS 2 链路")
                        }

                        Item { Layout.fillHeight: true }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            Repeater {
                                model: [
                                    { label: qsTr("启动"), action: "start" },
                                    { label: qsTr("状态"), action: "status" },
                                    { label: qsTr("等待"), action: "wait" },
                                    { label: qsTr("重启"), action: "restart" },
                                    { label: qsTr("停止"), action: "stop" }
                                ]
                                AppButton {
                                    required property var modelData
                                    Layout.fillWidth: true
                                    theme: root.theme
                                    text: modelData.label
                                    enabled: !root.controller.taskBusy
                                    onClicked: root.controller.manageRos(modelData.action)
                                }
                            }
                        }
                    }
                }

                GlassCard {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 310
                    theme: root.theme

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 9

                        SectionHeader {
                            Layout.fillWidth: true
                            theme: root.theme
                            title: qsTr("CAN / 电机")
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
                                enabled: root.controller.profile === "real" && !root.controller.taskBusy
                                onClicked: root.controller.runMaintenance("can_check", "")
                            }
                            AppButton {
                                Layout.fillWidth: true
                                theme: root.theme
                                text: qsTr("监听 5 秒")
                                enabled: root.controller.profile === "real"
                                         && !root.controller.connected && !root.controller.taskBusy
                                onClicked: root.controller.runMaintenance("motor_listen", "")
                            }
                            AppButton {
                                Layout.fillWidth: true
                                theme: root.theme
                                text: qsTr("扫描电机")
                                enabled: root.controller.profile === "real"
                                         && !root.controller.connected && !root.controller.taskBusy
                                onClicked: root.controller.runMaintenance("motor_scan", "")
                            }
                            AppButton {
                                Layout.fillWidth: true
                                theme: root.theme
                                text: qsTr("G1Z 混控测试")
                                enabled: root.controller.profile === "real"
                                         && !root.controller.connected && !root.controller.taskBusy
                                onClicked: root.controller.runMaintenance("gripper_test", "")
                            }
                        }

                        Item { Layout.fillHeight: true }

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
                            }
                            AppButton {
                                theme: root.theme
                                kind: "danger"
                                text: qsTr("六轴校零")
                                enabled: root.controller.profile === "real"
                                         && !root.controller.connected && !root.controller.taskBusy
                                onClicked: root.controller.runMaintenance(
                                               "set_zero_all", calibrationPhrase.text)
                            }
                            AppButton {
                                theme: root.theme
                                kind: "danger"
                                text: qsTr("夹爪校零")
                                enabled: root.controller.profile === "real"
                                         && !root.controller.connected && !root.controller.taskBusy
                                onClicked: root.controller.runMaintenance(
                                               "set_zero_gripper", calibrationPhrase.text)
                            }
                        }
                    }
                }
            }
        }

        GlassCard {
            id: logPanel

            property bool followTail: true
            readonly property Flickable logFlickable:
                logScroll.contentItem as Flickable

            function scrollToTail() {
                if (!logFlickable)
                    return

                logFlickable.contentY = Math.max(
                            0, logFlickable.contentHeight - logFlickable.height)
            }

            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredWidth: 0.46 * root.width
            theme: root.theme

            ColumnLayout {
                anchors.fill: parent
                spacing: 9

                RowLayout {
                    Layout.fillWidth: true

                    SectionHeader {
                        Layout.fillWidth: true
                        theme: root.theme
                        title: qsTr("运行日志")
                    }

                    AppButton {
                        theme: root.theme
                        kind: "quiet"
                        text: logPanel.followTail ? qsTr("暂停跟随")
                                                  : qsTr("跟随最新")
                        onClicked: {
                            logPanel.followTail = !logPanel.followTail
                            if (logPanel.followTail)
                                Qt.callLater(logPanel.scrollToTail)
                        }
                    }

                    AppButton {
                        theme: root.theme
                        kind: "quiet"
                        text: qsTr("清空")
                        onClicked: root.controller.clearLogs()
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    radius: root.theme.radiusControl
                    color: root.theme.logCanvas
                    border.width: 0

                    ScrollView {
                        id: logScroll
                        anchors.fill: parent
                        anchors.margins: 1
                        clip: true
                        ScrollBar.horizontal.policy: ScrollBar.AsNeeded
                        ScrollBar.vertical.policy: ScrollBar.AsNeeded

                        AppTextArea {
                            id: logs
                            width: Math.max(
                                       logScroll.availableWidth,
                                       contentWidth + leftPadding + rightPadding)
                            height: Math.max(
                                        logScroll.availableHeight,
                                        contentHeight + topPadding + bottomPadding)
                            readOnly: true
                            theme: root.theme
                            dark: true
                            text: root.controller.logs
                            wrapMode: TextArea.NoWrap
                            font.family: "monospace"
                            font.pixelSize: root.theme.typeCaption
                            background: null
                            onTextChanged: {
                                if (logPanel.followTail)
                                    Qt.callLater(logPanel.scrollToTail)
                            }
                        }
                    }
                }
            }
        }
    }
}
