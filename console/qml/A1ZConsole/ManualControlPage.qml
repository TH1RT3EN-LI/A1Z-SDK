pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Item {
    id: root
    objectName: "manualControlPage"

    required property var theme
    required property var controller
    property real motionSpeed: 0.5
    property real jointStepDeg: 2.0
    property real linearStepMm: 10.0
    property real angularStepDeg: 5.0
    property string frameMode: "base"
    property real gripperTargetDraft: 1.0
    property bool gripperTargetDirty: false
    property string gripperDraftProfile: ""

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

    function syncGripperDraft() {
        if (root.gripperDraftProfile !== root.controller.profile) {
            root.gripperDraftProfile = root.controller.profile
            root.gripperTargetDirty = false
        }

        var target = Number(root.controller.gripperTarget)
        if (root.gripperTargetDirty) {
            if (root.controller.commandBusy
                    || target < 0
                    || Math.abs(target - root.gripperTargetDraft) > 0.005) {
                return
            }
            root.gripperTargetDirty = false
        }

        if (target >= 0) {
            root.gripperTargetDraft = target
        } else if (root.controller.gripperMeasured >= 0) {
            root.gripperTargetDraft = Number(root.controller.gripperMeasured)
        }
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

            GlassCard {
                Layout.fillWidth: true
                Layout.preferredHeight: 112
                theme: root.theme

                RowLayout {
                    anchors.fill: parent
                    spacing: 10

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 3
                        Text {
                            text: qsTr("末端位姿")
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
                        Text {
                            Layout.fillWidth: true
                            text: root.controller.eeAxisText
                            color: root.theme.secondaryText
                            elide: Text.ElideRight
                            font.family: "monospace"
                            font.pixelSize: root.theme.typeCaption
                        }
                        Text {
                            Layout.fillWidth: true
                            text: root.controller.eeMotionText
                            color: root.theme.tertiaryText
                            elide: Text.ElideRight
                            font.family: root.theme.fontFamily
                            font.pixelSize: root.theme.typeCaption
                        }
                    }

                    AppButton {
                        theme: root.theme
                        text: qsTr("读取 FK")
                        enabled: root.controller.connected && !root.controller.commandBusy
                        onClicked: root.controller.refreshKinematics()
                    }
                }
            }

            GlassCard {
                Layout.fillWidth: true
                Layout.preferredHeight: 430
                theme: root.theme

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 8

                    RowLayout {
                        Layout.fillWidth: true

                        SectionHeader {
                            Layout.fillWidth: true
                            theme: root.theme
                            title: qsTr("关节控制")
                        }

                        AppButton {
                            theme: root.theme
                            text: qsTr("载入当前")
                            enabled: !root.controller.commandBusy
                            onClicked: root.loadCurrentDrafts()
                        }

                        AppButton {
                            theme: root.theme
                            kind: "primary"
                            text: qsTr("发送目标")
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
                                    qsTr("当前 °"),
                                    qsTr("限位 °"),
                                    qsTr("−"),
                                    qsTr("目标 °"),
                                    qsTr("+")
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
                                AppTextField {
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 1
                                    theme: root.theme
                                    text: draftModel.get(jointRow.index).target
                                    horizontalAlignment: Text.AlignHCenter
                                    validator: DoubleValidator {
                                        bottom: Number(jointRow.modelData.minimum)
                                        top: Number(jointRow.modelData.maximum)
                                        decimals: 3
                                        notation: DoubleValidator.StandardNotation
                                    }
                                    onTextEdited: draftModel.setProperty(jointRow.index, "target", text)
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
                            title: root.frameMode === "tool"
                                   ? qsTr("Tool 平移")
                                   : qsTr("Base 平移")
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
                                text: qsTr("+X")
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
                                text: qsTr("+Y")
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
                                text: qsTr("+Z")
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
                                text: qsTr("−Y")
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
                                text: qsTr("−X")
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
                                text: qsTr("−Z")
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
                            title: root.frameMode === "tool"
                                   ? qsTr("Tool 旋转")
                                   : qsTr("Base 旋转")
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
                Layout.preferredHeight: 190
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
                            text: root.controller.gripperMeasured < 0
                                  ? qsTr("实际 —")
                                  : qsTr("实际 %1").arg(
                                        root.controller.gripperMeasured.toFixed(3))
                            color: root.theme.secondaryText
                            font.family: root.theme.fontFamily
                            font.pixelSize: root.theme.typeLabel
                        }

                        AppSlider {
                            id: gripperDraft
                            objectName: "gripperTargetSlider"
                            Layout.fillWidth: true
                            theme: root.theme
                            from: 0.0
                            to: 1.0
                            value: root.gripperTargetDraft
                            stepSize: 0.01
                            enabled: root.controller.motionEnabled
                            Accessible.name: qsTr("夹爪目标开度")
                            onMoved: {
                                root.gripperTargetDraft = value
                                root.gripperTargetDirty = true
                            }
                        }

                        Text {
                            Layout.preferredWidth: 112
                            text: root.gripperTargetDirty
                                  ? qsTr("目标 %1 · 未发送").arg(
                                        root.gripperTargetDraft.toFixed(2))
                                  : qsTr("目标 %1").arg(
                                        root.gripperTargetDraft.toFixed(2))
                            color: root.gripperTargetDirty
                                   ? root.theme.orange : root.theme.text
                            font.family: "monospace"
                            font.pixelSize: root.theme.typeCaption
                        }

                        AppButton {
                            theme: root.theme
                            kind: "primary"
                            text: qsTr("发送目标")
                            enabled: root.controller.motionEnabled
                                     && root.gripperTargetDirty
                            onClicked: root.controller.setGripper(
                                           root.gripperTargetDraft)
                        }
                        AppButton {
                            theme: root.theme
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

    Connections {
        target: root.controller

        function onStateChanged() {
            root.syncGripperDraft()
        }
    }

    Component.onCompleted: {
        loadCurrentDrafts()
        syncGripperDraft()
    }
}
