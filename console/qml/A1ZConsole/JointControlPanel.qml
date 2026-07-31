pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

GlassCard {
    id: root
    objectName: "jointControlPanel"

    required property var controller
    property real motionSpeed: 0.5
    property real jointStepDeg: 2.0
    property bool jointDraftInitialized: false
    property bool jointDraftDirty: false
    property bool jointDraftValid: false
    property bool jointDraftStale: false
    property bool jointDraftWasConnected: false
    property string jointDraftProfile: ""
    readonly property bool draftPending: root.jointDraftDirty
    readonly property bool jointStateConfirmed:
        root.controller.connected
        && root.controller.backendMatched
        && root.controller.telemetryFresh
        && !root.controller.commandOutcomeUncertain
    readonly property var jointSnapshot:
        root.visible ? root.controller.joints : []
    readonly property var emptyJointData: ({
        name: "—",
        position: 0,
        minimum: 0,
        maximum: 0
    })

    implicitHeight: 430

    function loadCurrentDrafts() {
        if (root.jointDraftDirty
                || !root.jointStateConfirmed
                || root.jointSnapshot.length < 6)
            return
        const joints = root.jointSnapshot
        for (let i = 0; i < 6; ++i) {
            draftModel.setProperty(
                        i,
                        "target",
                        Number(joints[i].position).toFixed(2))
        }
        root.jointDraftInitialized = true
        root.jointDraftDirty = false
        root.jointDraftStale = false
        root.jointDraftWasConnected = true
        root.validateJointDrafts()
    }

    function syncJointDrafts() {
        if (root.jointDraftProfile !== root.controller.profile) {
            root.jointDraftProfile = root.controller.profile
            root.jointDraftInitialized = false
            root.jointDraftDirty = false
            root.jointDraftStale = false
            root.jointDraftWasConnected = false
        }
        if (!root.jointStateConfirmed) {
            if (root.jointDraftDirty)
                root.jointDraftStale = true
            else
                root.jointDraftInitialized = false
            root.jointDraftWasConnected = false
            root.validateJointDrafts()
            return
        }
        if (!root.jointDraftWasConnected) {
            root.jointDraftWasConnected = true
            if (root.jointDraftDirty) {
                root.jointDraftStale = true
                root.validateJointDrafts()
                return
            }
            root.jointDraftInitialized = false
        }
        if (!root.jointDraftInitialized)
            root.loadCurrentDrafts()
    }

    function submitDrafts() {
        const values = []
        for (let i = 0; i < 6; ++i)
            values.push(String(draftModel.get(i).target).trim())
        root.controller.sendJointTarget(values, root.motionSpeed)
    }

    function discardJointDraft() {
        root.jointDraftDirty = false
        root.jointDraftInitialized = false
        root.jointDraftStale = false
        root.validateJointDrafts()
        root.syncJointDrafts()
    }

    function validateJointDrafts() {
        let valid = root.jointDraftInitialized && !root.jointDraftStale
        const joints = root.jointSnapshot
        valid = valid && joints.length >= 6
        for (let i = 0; i < 6 && valid; ++i) {
            const raw = String(draftModel.get(i).target).trim()
            const value = Number(raw)
            const joint = joints[i]
            valid = raw.length > 0
                    && Number.isFinite(value)
                    && value >= Number(joint.minimum)
                    && value <= Number(joint.maximum)
        }
        root.jointDraftValid = valid
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

            Text {
                text: root.jointDraftStale
                      ? qsTr("连接已变化 · 请放弃旧目标后重新同步")
                      : !root.jointDraftInitialized
                        ? qsTr("等待当前姿态")
                        : root.jointDraftDirty && !root.jointDraftValid
                          ? qsTr("目标输入无效 · 运动已锁定")
                          : root.jointDraftDirty
                            ? qsTr("目标未发送 · 点动已锁定")
                            : qsTr("目标已同步")
                color: root.jointDraftDirty || root.jointDraftStale
                       ? root.theme.orange : root.theme.tertiaryText
                font.family: root.theme.fontFamily
                font.pixelSize: root.theme.typeCaption
            }

            AppButton {
                theme: root.theme
                text: qsTr("载入当前")
                enabled: root.controller.kinematicsReadEnabled
                         && !root.jointDraftDirty
                onClicked: root.loadCurrentDrafts()
            }

            AppButton {
                theme: root.theme
                kind: "primary"
                text: qsTr("发送目标")
                enabled: root.controller.motionEnabled
                         && root.jointDraftInitialized
                         && root.jointDraftDirty
                         && root.jointDraftValid
                onClicked: root.submitDrafts()
            }

            AppButton {
                objectName: "discardJointDraftButton"
                visible: root.jointDraftDirty || root.jointDraftStale
                theme: root.theme
                kind: "quiet"
                text: root.jointDraftStale
                      ? qsTr("放弃并重新载入")
                      : qsTr("放弃修改")
                enabled: !root.controller.commandBusy
                         && !root.controller.taskBusy
                         && !root.controller.emergencyBusy
                onClicked: root.discardJointDraft()
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
            model: 6

            JointControlRow {
                required property int index

                Layout.fillWidth: true
                Layout.preferredHeight: implicitHeight
                theme: root.theme
                controller: root.controller
                jointData: root.jointSnapshot.length > index
                           ? root.jointSnapshot[index] : root.emptyJointData
                jointIndex: index
                targetText: draftModel.get(index).target
                motionSpeed: root.motionSpeed
                jointStepDeg: root.jointStepDeg
                draftPending: root.jointDraftDirty
                draftInitialized: root.jointDraftInitialized
                draftStale: root.jointDraftStale
                onTargetEdited: function(value) {
                    draftModel.setProperty(index, "target", value)
                    root.jointDraftDirty = true
                    root.validateJointDrafts()
                }
            }
        }
    }

    Connections {
        target: root.controller

        function onStateChanged() {
            if (root.visible)
                root.syncJointDrafts()
        }

        function onJointTelemetryChanged() {
            if (root.visible) {
                root.validateJointDrafts()
                root.syncJointDrafts()
            }
        }

        function onTelemetryTimingChanged() {
            if (root.visible)
                root.syncJointDrafts()
        }

        function onArmPoseChanged() {
            root.jointDraftDirty = false
            root.jointDraftInitialized = false
            root.jointDraftStale = false
            root.validateJointDrafts()
        }

        function onArmStateInvalidated() {
            if (root.jointDraftDirty)
                root.jointDraftStale = true
            else
                root.jointDraftInitialized = false
            root.jointDraftWasConnected = false
            root.validateJointDrafts()
        }
    }

    onVisibleChanged: {
        if (visible)
            root.syncJointDrafts()
    }

    Component.onCompleted: root.syncJointDrafts()
}
