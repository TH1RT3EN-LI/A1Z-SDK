pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

GlassCard {
    id: root
    objectName: "graspPlanReviewPanel"

    required property var controller
    property real minimumReviewHeight: 260

    implicitHeight: Math.max(
                        reviewColumn.implicitHeight + 2 * root.padding,
                        root.minimumReviewHeight)

    ColumnLayout {
        id: reviewColumn

        anchors.fill: parent
        spacing: 9

        SectionHeader {
            Layout.fillWidth: true
            theme: root.theme
            title: qsTr("2. 审阅")
            subtitle: root.controller.planStatus
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 58
            visible: root.controller.planSegments.length > 0
            radius: root.theme.radiusControl
            color: root.theme.tile
            border.width: 0

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 2

                Text {
                    Layout.fillWidth: true
                    text: root.controller.graspSummary
                    textFormat: Text.PlainText
                    color: root.theme.text
                    elide: Text.ElideRight
                    font.family: root.theme.fontFamily
                    font.pixelSize: root.theme.typeLabel
                    font.weight: Font.DemiBold
                }

                Text {
                    Layout.fillWidth: true
                    text: qsTr("目标“%1” · %2 · Plan %3 · Frame %4")
                          .arg(root.controller.planInstruction || "—")
                          .arg(root.controller.planProfile.toUpperCase() || "—")
                          .arg(root.controller.planId || "—")
                          .arg(root.controller.planFrame || "—")
                    textFormat: Text.PlainText
                    color: root.theme.tertiaryText
                    elide: Text.ElideRight
                    font.family: root.theme.fontFamily
                    font.pixelSize: root.theme.typeCaption
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 410
            visible: root.controller.planSegments.length > 0
                     && root.controller.graspPreviewAvailable
            radius: root.theme.radiusControl
            color: root.theme.tile
            border.width: 0

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 7

                RowLayout {
                    Layout.fillWidth: true

                    Text {
                        Layout.fillWidth: true
                        text: qsTr("最终物体点云 + 夹爪 6-DoF")
                        color: root.theme.secondaryText
                        font.family: root.theme.fontFamily
                        font.pixelSize: root.theme.typeCaption
                        font.weight: Font.DemiBold
                    }

                    Text {
                        text: qsTr("红 X 接近 · 绿 Y 开口 · 蓝 Z 工具上")
                        color: root.theme.tertiaryText
                        font.family: root.theme.fontFamily
                        font.pixelSize: root.theme.typeCaption
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: root.theme.radiusSmall
                    color: "#0c121c"
                    clip: true

                    Image {
                        id: selectedGraspPointCloudPreview
                        objectName: "selectedGraspPointCloudPreview"

                        anchors.fill: parent
                        anchors.margins: 6
                        source: root.controller.graspPreviewSource
                        fillMode: Image.PreserveAspectFit
                        asynchronous: true
                        cache: false
                        smooth: true
                    }

                    Text {
                        anchors.centerIn: parent
                        visible: selectedGraspPointCloudPreview.status === Image.Error
                        text: qsTr("抓取点云预览无法载入")
                        color: root.theme.secondaryText
                        font.family: root.theme.fontFamily
                        font.pixelSize: root.theme.typeLabel
                    }
                }

                Text {
                    Layout.fillWidth: true
                    text: root.controller.graspBasePositionText
                    textFormat: Text.PlainText
                    color: root.theme.text
                    font.family: root.theme.fontFamily
                    font.pixelSize: root.theme.typeLabel
                    font.weight: Font.DemiBold
                }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            visible: root.controller.planSegments.length > 0
            spacing: 7

            RowLayout {
                Layout.fillWidth: true

                Text {
                    Layout.fillWidth: true
                    text: qsTr("安全检查")
                    color: root.theme.secondaryText
                    font.family: root.theme.fontFamily
                    font.pixelSize: root.theme.typeCaption
                }

                StatusPill {
                    theme: root.theme
                    text: root.controller.planSafetyPassed
                          ? qsTr("全部通过")
                          : qsTr("未通过")
                    level: root.controller.planSafetyPassed ? "ok" : "error"
                }
            }

            Flow {
                Layout.fillWidth: true
                Layout.preferredHeight: implicitHeight
                spacing: 7

                Repeater {
                    model: root.controller.planSafety

                    StatusPill {
                        required property var modelData

                        theme: root.theme
                        text: modelData.name
                        level: modelData.ok ? "ok" : "error"
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 30
            visible: root.controller.planSegments.length > 0
            radius: root.theme.radiusSmall
            color: root.theme.tile

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10

                Text {
                    Layout.preferredWidth: 100
                    text: qsTr("轨迹段")
                    color: root.theme.tertiaryText
                    font.family: root.theme.fontFamily
                    font.pixelSize: root.theme.typeCaption
                }

                Text {
                    Layout.fillWidth: true
                    text: qsTr("目标关节角（度）")
                    color: root.theme.tertiaryText
                    font.family: root.theme.fontFamily
                    font.pixelSize: root.theme.typeCaption
                }

                Text {
                    Layout.preferredWidth: 70
                    text: qsTr("超时")
                    color: root.theme.tertiaryText
                    horizontalAlignment: Text.AlignRight
                    font.family: root.theme.fontFamily
                    font.pixelSize: root.theme.typeCaption
                }
            }
        }

        Repeater {
            model: root.controller.planSegments

            GraspPlanSegmentRow {
                required property var modelData
                required property int index

                Layout.fillWidth: true
                Layout.preferredHeight: implicitHeight
                theme: root.theme
                segmentData: modelData
                lastRow: index === root.controller.planSegments.length - 1
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 90
            visible: root.controller.planSegments.length === 0

            Text {
                anchors.centerIn: parent
                text: root.controller.planState === "computing"
                      ? qsTr("正在计算计划…")
                      : root.controller.planState === "failed"
                        || root.controller.planState === "invalid"
                        ? root.controller.planStatus
                        : qsTr("暂无计划")
                textFormat: Text.PlainText
                color: root.theme.secondaryText
                font.family: root.theme.fontFamily
                font.pixelSize: root.theme.typeLabel
                font.weight: Font.DemiBold
            }
        }
    }
}
