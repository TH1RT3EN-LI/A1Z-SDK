pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

GlassCard {
    id: root
    objectName: "graspExecutionPanel"

    required property var controller
    property bool motionDraftPending: false
    readonly property bool actualExecutionAvailable:
        root.controller.planCurrent
        && root.controller.planSafetyPassed
        && root.controller.planExecutionEnabled
        && !root.motionDraftPending

    implicitHeight: Math.max(
                        root.motionDraftPending ? 145 : 120,
                        executionColumn.implicitHeight + 2 * root.padding)

    function clearConfirmation() {
        executePhrase.clear()
    }

    onActualExecutionAvailableChanged: {
        if (!root.actualExecutionAvailable)
            Qt.callLater(root.clearConfirmation)
    }

    ColumnLayout {
        id: executionColumn

        anchors.fill: parent
        spacing: 10

        SectionHeader {
            Layout.fillWidth: true
            theme: root.theme
            title: qsTr("3. 执行")
            subtitle: root.motionDraftPending
                      ? qsTr("有未发送控制目标；实际执行已锁定")
                      : root.controller.planState === "unsafe"
                        ? qsTr("安全检查未通过；仅允许无运动演练")
                        : !root.controller.planCurrent
                          ? qsTr("请先生成并审阅计划") : ""
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            AppTextField {
                id: executePhrase
                objectName: "graspExecutePhrase"

                Layout.fillWidth: true
                theme: root.theme
                placeholderText: qsTr("输入：执行 %1")
                                 .arg(root.controller.profile.toUpperCase())
                Accessible.name: qsTr("抓取执行确认短语")
                enabled: root.actualExecutionAvailable
            }

            AppButton {
                objectName: "dryRunGraspPlanButton"
                theme: root.theme
                text: root.controller.taskKind === "plan_dry_run"
                      ? qsTr("演练中…") : qsTr("演练")
                enabled: root.controller.planCurrent
                         && root.controller.planningEnabled
                onClicked: {
                    root.controller.executePlan(true, "")
                    root.clearConfirmation()
                }
            }

            AppButton {
                objectName: "executeGraspPlanButton"
                theme: root.theme
                kind: "danger"
                text: root.controller.taskKind === "plan_execute"
                      ? qsTr("执行中…") : qsTr("执行计划")
                enabled: root.actualExecutionAvailable
                         && executePhrase.text.trim()
                            === "执行 "
                                + root.controller.profile.toUpperCase()
                onClicked: {
                    root.controller.executePlan(false, executePhrase.text)
                    root.clearConfirmation()
                }
            }
        }
    }

    Connections {
        target: root.controller

        function onPlanChanged() {
            root.clearConfirmation()
        }
    }
}
