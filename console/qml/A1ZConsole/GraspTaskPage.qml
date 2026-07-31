pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

Item {
    id: root
    objectName: "graspTaskPage"

    required property var theme
    required property var controller
    property bool motionDraftPending: false
    readonly property bool actualExecutionAvailable:
        executionPanel.actualExecutionAvailable

    function clearExecutionConfirmation() {
        executionPanel.clearConfirmation()
    }

    onVisibleChanged: {
        if (!visible)
            root.clearExecutionConfirmation()
    }

    PageScrollView {
        id: graspScroll

        anchors.fill: parent

        ColumnLayout {
            width: graspScroll.availableWidth
            spacing: root.theme.spacingM

            GraspComputePanel {
                id: computePanel

                Layout.fillWidth: true
                Layout.preferredHeight: implicitHeight
                theme: root.theme
                controller: root.controller
            }

            GraspPlanReviewPanel {
                Layout.fillWidth: true
                Layout.preferredHeight: implicitHeight
                theme: root.theme
                controller: root.controller
                minimumReviewHeight: Math.max(
                                         260,
                                         root.height
                                         - computePanel.implicitHeight
                                         - executionPanel.implicitHeight
                                         - 2 * root.theme.spacingM)
            }

            GraspExecutionPanel {
                id: executionPanel

                Layout.fillWidth: true
                Layout.preferredHeight: implicitHeight
                theme: root.theme
                controller: root.controller
                motionDraftPending: root.motionDraftPending
            }
        }
    }
}
