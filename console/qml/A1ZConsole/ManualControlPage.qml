pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Item {
    id: root

    required property var theme
    required property var controller
    property real motionSpeed: 0.5
    property real jointStepDeg: 2.0
    property real linearStepMm: 10.0
    property real angularStepDeg: 5.0
    property string frameMode: "base"

    function loadCurrentDrafts() {
        for (var i = 0; i < 6; ++i)
            draftModel.setProperty(i, "target", Number(root.controller.joints[i].position).toFixed(2))
    }

    function submitDrafts() {
        var values = []
        for (var i = 0; i < 6; ++i)
            values.push(Number(draftModel.get(i).target))
        root.controller.sendJointTarget(values, root.motionSpeed)
    }

    ListModel {
        id: draftModel
        ListElement { target: "0.00" }
        ListElement { target: "0.00" }
        ListElement { target: "0.00" }
        ListElement { target: "0.00" }
        ListElement { target: "0.00" }
        ListElement { target: "0.00" }
    }

    ScrollView {
        anchors.fill: parent
        clip: true

        ColumnLayout {
            width: root.width
            spacing: root.theme.spacingM

            SectionHeader {
                Layout.fillWidth: true
                theme: root.theme
                title: qsTr("手动控制")
            }

            GlassCard {
                Layout.fillWidth: true
                Layout.preferredHeight: 86
                theme: root.theme

                RowLayout {
                    anchors.fill: parent
                    spacing: 10

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 3
                        Text {
                            text: qsTr("末端 grasp_tcp 回读")
                            color: root.theme.tertiaryText
                            font.family: root.theme.fontFamily
                            font.pixelSize: root.theme.typeCaption
                        }
                        Text {
                            Layout.fillWidth: true
                            text: root.controller.eePoseText
                            color: root.theme.text
                            elide: Text.ElideRight
                            font.family: "monospace"
                            font.pixelSize: root.theme.typeLabel
                            font.weight: Font.DemiBold
                        }
                    }

                    AppButton {
                        theme: root.theme
                        text: qsTr("读取一次 FK")
                        enabled: root.controller.connected && !root.controller.commandBusy
                        onClicked: root.controller.refreshKinematics()
                    }
                }
            }

            GlassCard {
                Layout.fillWidth: true
                Layout.preferredHeight: 390
                theme: root.theme

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 8

                    RowLayout {
                        Layout.fillWidth: true

                        SectionHeader {
                            Layout.fillWidth: true
                            theme: root.theme
                            title: qsTr("单关节点动与绝对目标")
                        }

                        AppButton {
                            theme: root.theme
                            text: qsTr("载入当前值")
                            enabled: !root.controller.commandBusy
                            onClicked: root.loadCurrentDrafts()
                        }

                        AppButton {
                            theme: root.theme
                            kind: "primary"
                            text: qsTr("发送一次绝对运动")
                            enabled: root.controller.motionEnabled
                            onClicked: root.submitDrafts()
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 30
                        radius: root.theme.radiusSmall
                        color: root.theme.tile

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            spacing: 7

                            Repeater {
                                model: [
                                    qsTr("关节"),
                                    qsTr("回读角度"),
                                    qsTr("软限位"),
                                    qsTr("负向一步"),
                                    qsTr("目标草稿"),
                                    qsTr("正向一步")
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
                            Layout.preferredHeight: 44
                            radius: root.theme.radiusSmall
                            color: jointRow.index % 2 ? root.theme.tile : "transparent"

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 10
                                spacing: 7

                                Text {
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 1
                                    text: jointRow.modelData.name
                                    color: root.theme.text
                                    horizontalAlignment: Text.AlignHCenter
                                    font.family: root.theme.fontFamily
                                    font.pixelSize: root.theme.typeLabel
                                    font.weight: Font.Bold
                                }
                                Text {
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 1
                                    text: Number(jointRow.modelData.position).toFixed(2) + "°"
                                    color: root.theme.text
                                    horizontalAlignment: Text.AlignHCenter
                                    font.family: "monospace"
                                    font.pixelSize: root.theme.typeLabel
                                }
                                Text {
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 1
                                    text: "[" + Number(jointRow.modelData.minimum).toFixed(0)
                                          + ", " + Number(jointRow.modelData.maximum).toFixed(0) + "]"
                                    color: root.theme.tertiaryText
                                    horizontalAlignment: Text.AlignHCenter
                                    font.family: "monospace"
                                    font.pixelSize: root.theme.typeCaption
                                }
                                AppButton {
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 1
                                    theme: root.theme
                                    text: "− " + root.jointStepDeg.toFixed(1) + "°"
                                    enabled: root.controller.motionEnabled
                                    onClicked: root.controller.jogJoint(jointRow.index, -root.jointStepDeg,
                                                                root.motionSpeed)
                                }
                                TextField {
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 1
                                    text: draftModel.get(jointRow.index).target
                                    color: root.theme.text
                                    selectByMouse: true
                                    horizontalAlignment: Text.AlignHCenter
                                    validator: DoubleValidator {
                                        bottom: Number(jointRow.modelData.minimum)
                                        top: Number(jointRow.modelData.maximum)
                                        decimals: 3
                                        notation: DoubleValidator.StandardNotation
                                    }
                                    onTextEdited: draftModel.setProperty(jointRow.index, "target", text)
                                    background: Rectangle {
                                        radius: root.theme.radiusSmall
                                        color: root.theme.control
                                        border.color: parent.activeFocus
                                                      ? root.theme.accent : root.theme.border
                                    }
                                }
                                AppButton {
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 1
                                    theme: root.theme
                                    text: "+ " + root.jointStepDeg.toFixed(1) + "°"
                                    enabled: root.controller.motionEnabled
                                    onClicked: root.controller.jogJoint(jointRow.index, root.jointStepDeg,
                                                                root.motionSpeed)
                                }
                            }
                        }
                    }
                }
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 2
                columnSpacing: root.theme.spacingM
                rowSpacing: root.theme.spacingM

                GlassCard {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 320
                    theme: root.theme

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 9

                        SectionHeader {
                            Layout.fillWidth: true
                            theme: root.theme
                            title: qsTr("末端平移")
                        }

                        GridLayout {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            columns: 3
                            columnSpacing: 8
                            rowSpacing: 8

                            Item { Layout.fillWidth: true; Layout.fillHeight: true }
                            AppButton {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                theme: root.theme
                                text: qsTr("+X 前")
                                enabled: root.controller.motionEnabled
                                onClicked: root.controller.jogCartesian(
                                               "translation", "x",
                                               root.linearStepMm / 1000.0,
                                               root.frameMode, root.motionSpeed)
                            }
                            Item { Layout.fillWidth: true; Layout.fillHeight: true }

                            AppButton {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                theme: root.theme
                                text: qsTr("+Y 左")
                                enabled: root.controller.motionEnabled
                                onClicked: root.controller.jogCartesian(
                                               "translation", "y",
                                               root.linearStepMm / 1000.0,
                                               root.frameMode, root.motionSpeed)
                            }
                            AppButton {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                theme: root.theme
                                kind: "primary"
                                text: qsTr("+Z 上")
                                enabled: root.controller.motionEnabled
                                onClicked: root.controller.jogCartesian(
                                               "translation", "z",
                                               root.linearStepMm / 1000.0,
                                               root.frameMode, root.motionSpeed)
                            }
                            AppButton {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                theme: root.theme
                                text: qsTr("−Y 右")
                                enabled: root.controller.motionEnabled
                                onClicked: root.controller.jogCartesian(
                                               "translation", "y",
                                               -root.linearStepMm / 1000.0,
                                               root.frameMode, root.motionSpeed)
                            }

                            Item { Layout.fillWidth: true; Layout.fillHeight: true }
                            AppButton {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                theme: root.theme
                                text: qsTr("−X 后")
                                enabled: root.controller.motionEnabled
                                onClicked: root.controller.jogCartesian(
                                               "translation", "x",
                                               -root.linearStepMm / 1000.0,
                                               root.frameMode, root.motionSpeed)
                            }
                            Item { Layout.fillWidth: true; Layout.fillHeight: true }

                            Item { Layout.fillWidth: true; Layout.fillHeight: true }
                            AppButton {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                theme: root.theme
                                text: qsTr("−Z 下")
                                enabled: root.controller.motionEnabled
                                onClicked: root.controller.jogCartesian(
                                               "translation", "z",
                                               -root.linearStepMm / 1000.0,
                                               root.frameMode, root.motionSpeed)
                            }
                            Item { Layout.fillWidth: true; Layout.fillHeight: true }
                        }
                    }
                }

                GlassCard {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 320
                    theme: root.theme

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 9

                        SectionHeader {
                            Layout.fillWidth: true
                            theme: root.theme
                            title: qsTr("末端姿态")
                        }

                        Repeater {
                            model: [
                                { "label": "Roll", "axis": "x" },
                                { "label": "Pitch", "axis": "y" },
                                { "label": "Yaw", "axis": "z" }
                            ]

                            RowLayout {
                                id: rotationRow
                                required property var modelData
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                spacing: 8

                                Text {
                                    Layout.preferredWidth: 54
                                    text: rotationRow.modelData.label
                                    color: root.theme.secondaryText
                                    font.family: root.theme.fontFamily
                                    font.pixelSize: root.theme.typeLabel
                                    font.weight: Font.DemiBold
                                }
                                AppButton {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    theme: root.theme
                                    text: "− " + root.angularStepDeg.toFixed(1) + "°"
                                    enabled: root.controller.motionEnabled
                                    onClicked: root.controller.jogCartesian(
                                                   "rotation", rotationRow.modelData.axis,
                                                   -root.angularStepDeg,
                                                   root.frameMode, root.motionSpeed)
                                }
                                AppButton {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    theme: root.theme
                                    text: "+ " + root.angularStepDeg.toFixed(1) + "°"
                                    enabled: root.controller.motionEnabled
                                    onClicked: root.controller.jogCartesian(
                                                   "rotation", rotationRow.modelData.axis,
                                                   root.angularStepDeg,
                                                   root.frameMode, root.motionSpeed)
                                }
                            }
                        }
                    }
                }
            }

            GlassCard {
                Layout.fillWidth: true
                Layout.preferredHeight: 170
                theme: root.theme

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 9

                    SectionHeader {
                        Layout.fillWidth: true
                        theme: root.theme
                        title: qsTr("G1Z 夹爪")
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        Text {
                            text: root.controller.gripper < 0 ? qsTr("回读 —")
                                                      : qsTr("回读 %1").arg(root.controller.gripper.toFixed(3))
                            color: root.theme.secondaryText
                            font.family: root.theme.fontFamily
                            font.pixelSize: root.theme.typeLabel
                        }

                        Slider {
                            id: gripperDraft
                            Layout.fillWidth: true
                            from: 0.0
                            to: 1.0
                            value: root.controller.gripper < 0 ? 1.0 : root.controller.gripper
                            stepSize: 0.01
                        }

                        Text {
                            text: gripperDraft.value.toFixed(2)
                            color: root.theme.text
                            font.family: "monospace"
                            font.pixelSize: root.theme.typeLabel
                        }

                        AppButton {
                            theme: root.theme
                            kind: "primary"
                            text: qsTr("发送开度")
                            enabled: root.controller.motionEnabled
                            onClicked: root.controller.setGripper(gripperDraft.value)
                        }
                        AppButton {
                            theme: root.theme
                            kind: "success"
                            text: qsTr("夹持检测")
                            enabled: root.controller.motionEnabled
                            onClicked: root.controller.graspClose()
                        }
                        AppButton {
                            theme: root.theme
                            text: qsTr("释放")
                            enabled: root.controller.motionEnabled
                            onClicked: root.controller.graspRelease()
                        }
                    }
                }
            }
        }
    }

    Component.onCompleted: loadCurrentDrafts()
}
